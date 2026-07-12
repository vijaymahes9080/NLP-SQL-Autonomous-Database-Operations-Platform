import os
import json
import uuid
import datetime
from typing import List, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from backend.config import settings
from backend.database import vault, DBExecutor

scheduler = BackgroundScheduler()
scheduler.start()

class WorkflowEngine:
    def __init__(self, filepath: str = settings.WORKFLOWS_PATH):
        self.filepath = filepath
        self._ensure_storage_exists()
        self.reload_schedules()

    def _ensure_storage_exists(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump({"workflows": []}, f, indent=4)

    def get_workflows(self) -> List[Dict[str, Any]]:
        with open(self.filepath, "r") as f:
            return json.load(f).get("workflows", [])

    def save_workflows(self, workflows: List[Dict[str, Any]]):
        with open(self.filepath, "w") as f:
            json.dump({"workflows": workflows}, f, indent=4)

    def add_workflow(self, name: str, connection_id: str, query: str, trigger_type: str, cron_expr: str, actions: List[Dict[str, Any]]) -> str:
        """
        Actions can be: {"type": "email", "to": "admin@org.com"} or {"type": "webhook", "url": "https://api.site/endpoint"}
        """
        workflows = self.get_workflows()
        w_id = f"flow_{str(uuid.uuid4())[:8]}"
        
        new_flow = {
            "id": w_id,
            "name": name,
            "connection_id": connection_id,
            "query": query,
            "trigger_type": trigger_type, # "cron" or "event"
            "cron_expr": cron_expr, # e.g. "0 0 * * *" (daily), "*/5 * * * *"
            "actions": actions,
            "active": True,
            "last_run": None,
            "next_run": None
        }
        
        workflows.append(new_flow)
        self.save_workflows(workflows)
        self.reload_schedules()
        return w_id

    def delete_workflow(self, w_id: str) -> bool:
        workflows = self.get_workflows()
        filtered = [w for w in workflows if w["id"] != w_id]
        if len(filtered) == len(workflows):
            return False
            
        self.save_workflows(filtered)
        self.reload_schedules()
        return True

    def toggle_workflow(self, w_id: str, active: bool) -> bool:
        workflows = self.get_workflows()
        found = False
        for w in workflows:
            if w["id"] == w_id:
                w["active"] = active
                found = True
        if found:
            self.save_workflows(workflows)
            self.reload_schedules()
        return found

    def run_workflow_task(self, flow_id: str):
        # Retrieve workflow details
        workflows = self.get_workflows()
        flow = next((w for w in workflows if w["id"] == flow_id), None)
        if not flow or not flow["active"]:
            return
            
        conn_id = flow["connection_id"]
        query = flow["query"]
        
        # Load connection configuration
        conns = vault.get_connections()
        conn = next((c for c in conns if c["id"] == conn_id), None)
        if not conn:
            self.log_execution(flow_id, False, "Connection config not found in vault")
            return
            
        # Execute query
        res = DBExecutor.execute_query(conn["type"], conn["config"], query)
        
        if not res.get("success", False):
            self.log_execution(flow_id, False, f"Query execution failed: {res.get('error')}")
            return
            
        # Success! Trigger actions
        action_logs = []
        for action in flow.get("actions", []):
            a_type = action.get("type")
            if a_type == "email":
                action_logs.append(f"Mock Email sent to {action.get('to')} containing {res.get('rows_affected')} items.")
            elif a_type == "webhook":
                action_logs.append(f"Mock Webhook dispatched to {action.get('url')} status: 200 OK.")
                
        # Update last run date
        now_str = datetime.datetime.now().isoformat()
        for w in workflows:
            if w["id"] == flow_id:
                w["last_run"] = now_str
                
        self.save_workflows(workflows)
        self.log_execution(flow_id, True, f"Success. Actions taken: {', '.join(action_logs)}")

    def log_execution(self, flow_id: str, success: bool, log_message: str):
        audit_path = settings.AUDIT_LOG_PATH
        logs = []
        if os.path.exists(audit_path):
            try:
                with open(audit_path, "r") as f:
                    logs = json.load(f)
            except:
                pass
                
        new_log = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": "WORKFLOW_EXECUTION",
            "flow_id": flow_id,
            "success": success,
            "detail": log_message
        }
        
        logs.append(new_log)
        with open(audit_path, "w") as f:
            json.dump(logs[-500:], f, indent=4) # keep last 500 audit logs

    def reload_schedules(self):
        """
        Clears current scheduler jobs and reschedules all active workflow cron tasks.
        """
        scheduler.remove_all_jobs()
        workflows = self.get_workflows()
        
        for w in workflows:
            if not w["active"]:
                continue
                
            cron = w["cron_expr"]
            # Minimal translation of 5-field cron notation to apscheduler format
            try:
                fields = cron.split()
                if len(fields) == 5:
                    minute, hour, day, month, day_of_week = fields
                    # Standardize fields mapping for background executor
                    scheduler.add_job(
                        self.run_workflow_task,
                        trigger='cron',
                        minute=minute,
                        hour=hour,
                        day=day,
                        month=month,
                        day_of_week=day_of_week,
                        args=[w["id"]],
                        id=w["id"]
                    )
            except Exception as e:
                # Log error scheduling cron
                self.log_execution(w["id"], False, f"Failed to register schedule details: {str(e)}")

workflow_engine = WorkflowEngine()
