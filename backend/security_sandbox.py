import os
import shutil
import tempfile
import sqlite3
import time
from typing import Dict, Any, Tuple
from backend.config import settings
from backend.database import DBExecutor

class SecuritySandbox:
    @staticmethod
    def get_query_type(query: str) -> str:
        query_upper = query.strip().upper()
        if query_upper.startswith("SELECT") or query_upper.startswith("WITH"):
            return "READ"
        elif any(query_upper.startswith(w) for w in ["INSERT", "UPDATE", "DELETE", "REPLACE"]):
            return "WRITE"
        elif any(query_upper.startswith(w) for w in ["CREATE", "DROP", "ALTER", "TRUNCATE"]):
            return "SCHEMA"
        else:
            return "UNKNOWN"

    @staticmethod
    def estimate_performance_cost(db_type: str, config: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Attempts to run explain plan to evaluate index scans and query complexity.
        """
        cost_score = "Low"
        plan = []
        duration_ms = 0.0
        
        if db_type == "sqlite":
            path = config.get("database_path", "")
            if os.path.exists(path):
                try:
                    conn = sqlite3.connect(path)
                    cursor = conn.cursor()
                    
                    # Run EXPLAIN QUERY PLAN
                    t_start = time.perf_counter()
                    cursor.execute(f"EXPLAIN QUERY PLAN {query}")
                    plan_rows = cursor.fetchall()
                    t_end = time.perf_counter()
                    duration_ms = (t_end - t_start) * 1000.0
                    
                    plan = [row[3] for row in plan_rows]
                    
                    # If SCAN TABLE is present, flag as medium/high cost (no index)
                    if any("SCAN" in str(p) for p in plan):
                        cost_score = "Medium"
                    if any("TEMP B-TREE" in str(p) for p in plan):
                        cost_score = "High (Temp B-tree sort)"
                        
                    conn.close()
                except Exception as e:
                    plan = [f"Explain failed: {str(e)}"]
                    
        return {
            "cost_score": cost_score,
            "query_plan": plan,
            "explain_duration_ms": round(duration_ms, 2)
        }

    @classmethod
    def execute_with_sandbox(cls, db_type: str, config: Dict[str, Any], query: str, mode: str) -> Dict[str, Any]:
        """
        Runs query through safety filters based on selected mode.
        Modes: SAFE, APPROVAL, SANDBOX, AUTONOMOUS
        """
        query_type = cls.get_query_type(query)
        
        # 1. Evaluate performance estimation
        perf_est = cls.estimate_performance_cost(db_type, config, query)
        
        # 2. Check restrictions based on mode
        if mode == "SAFE" and query_type != "READ":
            return {
                "success": False,
                "error": f"Execution Blocked: Database is configured in SAFE mode. '{query_type}' operations are restricted.",
                "mode": mode,
                "query_type": query_type
            }
            
        # If write query in APPROVAL mode, wait for front-end approval marker
        if mode == "APPROVAL" and query_type != "READ":
            # Note: The api endpoint will return that approval is required
            # Frontend must send confirmation flag 'approved': true to bypass
            return {
                "success": False,
                "approval_required": True,
                "message": f"Security Notice: This query modifies data. Please approve execution.",
                "estimated_cost": perf_est["cost_score"]
            }

        # 3. SANDBOX MODE execution (SQLite exclusive cloning)
        if mode == "SANDBOX" and db_type == "sqlite" and query_type != "READ":
            original_path = config.get("database_path", "")
            if not original_path or not os.path.exists(original_path):
                return {"success": False, "error": "Sandbox original database file not found"}
                
            # Create a temporary file and copy current DB state
            temp_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
            os.close(temp_fd)
            shutil.copy2(original_path, temp_db_path)
            
            # Execute on the replica
            sandbox_config = {"database_path": temp_db_path}
            t_start = time.perf_counter()
            res = DBExecutor.execute_query("sqlite", sandbox_config, query)
            t_end = time.perf_counter()
            duration_ms = (t_end - t_start) * 1000.0
            
            # Clean up temporary database replica
            try:
                os.remove(temp_db_path)
            except:
                pass
                
            res["sandbox_simulated"] = True
            res["duration_ms"] = round(duration_ms, 2)
            res["performance"] = perf_est
            res["message"] = "Simulated execution completed in a isolated sandbox container. No changes were saved."
            return res

        # 4. Standard execution (Directly database commit)
        t_start = time.perf_counter()
        res = DBExecutor.execute_query(db_type, config, query)
        t_end = time.perf_counter()
        duration_ms = (t_end - t_start) * 1000.0
        
        res["sandbox_simulated"] = False
        res["duration_ms"] = round(duration_ms, 2)
        res["performance"] = perf_est
        return res
