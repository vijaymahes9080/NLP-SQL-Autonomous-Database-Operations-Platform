import os
import json
import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.database import vault, DBExecutor
from backend.vector_store import schema_store
from backend.agents import orchestrator, AnalyticsAgent
from backend.security_sandbox import SecuritySandbox
from backend.workflows import workflow_engine

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

# Enable CORS for Next.js app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit log helper
def add_audit_log(event_type: str, detail: str, user: str = "admin", status: str = "success"):
    audit_path = settings.AUDIT_LOG_PATH
    logs = []
    if os.path.exists(audit_path):
        try:
            with open(audit_path, "r") as f:
                logs = json.load(f)
        except:
            pass
            
    logs.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "event_type": event_type,
        "detail": detail,
        "user": user,
        "status": status
    })
    
    with open(audit_path, "w") as f:
        json.dump(logs[-500:], f, indent=4) # keep last 500

# Input Models
class ConnectionModel(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]

class CopilotQueryModel(BaseModel):
    user_query: str
    connection_id: str
    chat_history: Optional[List[Dict[str, str]]] = []

class QueryExecuteModel(BaseModel):
    connection_id: str
    query: str
    mode: str = "APPROVAL"
    approved: bool = False

class WorkflowModel(BaseModel):
    name: str
    connection_id: str
    query: str
    trigger_type: str
    cron_expr: str
    actions: List[Dict[str, Any]]

# Endpoints
@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "gemini_enabled": bool(settings.GEMINI_API_KEY)
    }

# Connections
@app.get("/api/v1/connections")
def list_connections():
    return vault.get_connections()

@app.post("/api/v1/connections")
def create_connection(conn: ConnectionModel):
    # Test connection before adding
    ok, msg = DBExecutor.test_connection(conn.type, conn.config)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Database connection validation failed: {msg}")
        
    conn_id = vault.add_connection(conn.name, conn.type, conn.config)
    
    # Trigger initial schema index
    try:
        schema = DBExecutor.get_schema(conn.type, conn.config)
        schema_store.index_database_schema(conn_id, schema)
    except Exception as e:
        # Ignore schema index failure on save; can be rescanned later
        pass
        
    add_audit_log("CONNECTION_CREATED", f"Added connection {conn.name} ({conn.type})")
    return {"id": conn_id, "status": "connected", "message": msg}

@app.post("/api/v1/connections/test")
def test_connection(conn: ConnectionModel):
    ok, msg = DBExecutor.test_connection(conn.type, conn.config)
    return {"success": ok, "message": msg}

@app.delete("/api/v1/connections/{conn_id}")
def delete_connection(conn_id: str):
    conns = vault.get_connections()
    conn = next((c for c in conns if c["id"] == conn_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    ok = vault.delete_connection(conn_id)
    add_audit_log("CONNECTION_DELETED", f"Deleted connection: {conn.get('name')}")
    return {"success": ok}

@app.post("/api/v1/connections/{conn_id}/rescan")
def rescan_connection_schema(conn_id: str):
    conns = vault.get_connections()
    conn = next((c for c in conns if c["id"] == conn_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    try:
        schema = DBExecutor.get_schema(conn["type"], conn["config"])
        schema_store.index_database_schema(conn_id, schema)
        add_audit_log("SCHEMA_RESCAN", f"Rescanned database schema for: {conn.get('name')}")
        return {"success": True, "tables_count": len(schema), "schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema extraction error: {str(e)}")

# NLP Query Generation
@app.post("/api/v1/query/copilot")
def copilot_query(payload: CopilotQueryModel):
    conns = vault.get_connections()
    conn = next((c for c in conns if c["id"] == payload.connection_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Database connection configuration not found")
        
    try:
        res = orchestrator.process_message(
            user_query=payload.user_query,
            conn_id=payload.connection_id,
            vault_connections=conns,
            chat_history=payload.chat_history
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copilot logic error: {str(e)}")

# Safe SQL Execution
@app.post("/api/v1/query/execute")
def execute_query(payload: QueryExecuteModel):
    conns = vault.get_connections()
    conn = next((c for c in conns if c["id"] == payload.connection_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Database connection configuration not found")
        
    query_type = SecuritySandbox.get_query_type(payload.query)
    
    # If the action modifies data, check approval level
    if payload.mode == "APPROVAL" and query_type != "READ" and not payload.approved:
        # Halt execution, report safety check to client
        perf_est = SecuritySandbox.estimate_performance_cost(conn["type"], conn["config"], payload.query)
        add_audit_log("EXECUTION_BLOCKED", f"Write Query modification intercepted. Pending User approval.", status="warning")
        return {
            "success": False,
            "approval_required": True,
            "message": "This query alters database records. Please verify statement before execution.",
            "query": payload.query,
            "query_type": query_type,
            "estimated_cost": perf_est["cost_score"]
        }
        
    # Execute query using Security Sandbox (which clones SQLite database if in SANDBOX mode)
    try:
        res = SecuritySandbox.execute_with_sandbox(
            db_type=conn["type"],
            config=conn["config"],
            query=payload.query,
            mode=payload.mode
        )
        
        if not res.get("success", False):
            add_audit_log("QUERY_FAILED", f"Query executed with error: {res.get('error')}", status="failed")
            return res
            
        # Post-execution analytics using the AnalyticsAgent
        rows = res.get("rows", [])
        cols = res.get("columns", [])
        
        # Only run analytics if data was retrieved
        analytics_data = {}
        if len(rows) > 0 and len(cols) > 0:
            try:
                analyst = AnalyticsAgent()
                analytics_data = analyst.analyze_results("Execute query", payload.query, cols, rows)
            except Exception as e:
                # fallback values
                analytics_data = {
                    "summary": f"Query executed successfully, returning {len(rows)} rows.",
                    "chart_type": "table",
                    "chart_title": "Query Results",
                    "x_axis_field": "",
                    "y_axis_fields": [],
                    "kpis": [{"label": "Rows count", "value": str(len(rows))}]
                }
                
        res["analytics"] = analytics_data
        add_audit_log("QUERY_EXECUTED", f"Successfully executed query. Affected rows: {res.get('rows_affected')}")
        return res
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database execution crash: {str(e)}")

# Agentic Workflows
@app.get("/api/v1/workflows")
def list_workflows():
    return workflow_engine.get_workflows()

@app.post("/api/v1/workflows")
def create_workflow(w: WorkflowModel):
    w_id = workflow_engine.add_workflow(
        name=w.name,
        connection_id=w.connection_id,
        query=w.query,
        trigger_type=w.trigger_type,
        cron_expr=w.cron_expr,
        actions=w.actions
    )
    add_audit_log("WORKFLOW_CREATED", f"Added automation workflow: {w.name} ({w_id})")
    return {"id": w_id, "status": "active"}

@app.delete("/api/v1/workflows/{w_id}")
def delete_workflow(w_id: str):
    ok = workflow_engine.delete_workflow(w_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    add_audit_log("WORKFLOW_DELETED", f"Deleted workflow ID {w_id}")
    return {"success": True}

@app.post("/api/v1/workflows/{w_id}/toggle")
def toggle_workflow(w_id: str, active: bool = Query(..., description="Active state")):
    ok = workflow_engine.toggle_workflow(w_id, active)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found")
    add_audit_log("WORKFLOW_TOGGLED", f"Toggled workflow {w_id} to active={active}")
    return {"success": True}

@app.post("/api/v1/workflows/{w_id}/run")
def trigger_workflow_manually(w_id: str):
    try:
        workflow_engine.run_workflow_task(w_id)
        return {"success": True, "message": "Workflow task triggered successfully in background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Audit Logs
@app.get("/api/v1/audit-logs")
def get_audit_logs():
    audit_path = settings.AUDIT_LOG_PATH
    if os.path.exists(audit_path):
        try:
            with open(audit_path, "r") as f:
                return json.load(f)
        except:
            return []
    return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
