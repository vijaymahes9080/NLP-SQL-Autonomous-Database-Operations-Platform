import os
import json
import shutil
import sqlite3
import datetime
from typing import Dict, Any, List
from backend.config import settings
from backend.database import DBExecutor

class TimeMachineManager:
    SNAPSHOTS_DIR = os.path.join(settings.WORKSPACE_DIR, "snapshots")
    INDEX_FILE = os.path.join(SNAPSHOTS_DIR, "snapshots.json")

    @classmethod
    def _ensure_snapshots_dir(cls):
        if not os.path.exists(cls.SNAPSHOTS_DIR):
            os.makedirs(cls.SNAPSHOTS_DIR)
        if not os.path.exists(cls.INDEX_FILE):
            with open(cls.INDEX_FILE, "w") as f:
                json.dump({"snapshots": []}, f, indent=4)

    @classmethod
    def get_snapshots(cls, conn_id: str) -> List[Dict[str, Any]]:
        cls._ensure_snapshots_dir()
        try:
            with open(cls.INDEX_FILE, "r") as f:
                data = json.load(f)
            return [s for s in data.get("snapshots", []) if s["connection_id"] == conn_id]
        except Exception:
            return []

    @classmethod
    def _save_all_snapshots(cls, snapshots: List[Dict[str, Any]]):
        cls._ensure_snapshots_dir()
        with open(cls.INDEX_FILE, "w") as f:
            json.dump({"snapshots": snapshots}, f, indent=4)

    @classmethod
    def create_snapshot(cls, conn_id: str, db_type: str, config: Dict[str, Any], label: str) -> Dict[str, Any]:
        cls._ensure_snapshots_dir()
        
        if db_type != "sqlite":
            return {"success": False, "error": "Time Machine snapshots are currently only supported for SQLite connections."}

        original_path = config.get("database_path", "")
        if not original_path or not os.path.exists(original_path):
            return {"success": False, "error": "Primary database file not found"}

        snapshot_id = f"snap_{int(os.urandom(4).hex(), 16)}"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"{conn_id}_{timestamp}_{snapshot_id}.db"
        snapshot_path = os.path.join(cls.SNAPSHOTS_DIR, snapshot_filename)

        try:
            # Copy database file
            shutil.copy2(original_path, snapshot_path)

            # Record in index
            with open(cls.INDEX_FILE, "r") as f:
                data = json.load(f)
            
            snapshots = data.get("snapshots", [])
            new_snap = {
                "id": snapshot_id,
                "connection_id": conn_id,
                "label": label,
                "timestamp": datetime.datetime.now().isoformat(),
                "filename": snapshot_filename,
                "path": snapshot_path,
                "db_type": db_type
            }
            snapshots.append(new_snap)
            cls._save_all_snapshots(snapshots)

            return {"success": True, "snapshot": new_snap}
        except Exception as e:
            return {"success": False, "error": f"Failed to take database snapshot: {str(e)}"}

    @classmethod
    def query_snapshot(cls, snapshot_id: str, query: str) -> Dict[str, Any]:
        cls._ensure_snapshots_dir()
        with open(cls.INDEX_FILE, "r") as f:
            data = json.load(f)
        
        snap = next((s for s in data.get("snapshots", []) if s["id"] == snapshot_id), None)
        if not snap:
            return {"success": False, "error": "Snapshot not found"}

        snapshot_path = snap["path"]
        if not os.path.exists(snapshot_path):
            return {"success": False, "error": f"Snapshot database file is missing on disk at: {snapshot_path}"}

        # Run query on the static snapshot path
        snapshot_config = {"database_path": snapshot_path}
        res = DBExecutor.execute_query("sqlite", snapshot_config, query)
        res["snapshot_simulated"] = True
        res["message"] = f"Query executed successfully against Snapshot Time Machine checkpoint: '{snap.get('label')}'."
        return res

    @classmethod
    def restore_snapshot(cls, snapshot_id: str, db_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        cls._ensure_snapshots_dir()
        with open(cls.INDEX_FILE, "r") as f:
            data = json.load(f)
            
        snap = next((s for s in data.get("snapshots", []) if s["id"] == snapshot_id), None)
        if not snap:
            return {"success": False, "error": "Snapshot not found"}

        if db_type != "sqlite":
            return {"success": False, "error": "Snapshot restore is only supported for SQLite."}

        original_path = config.get("database_path", "")
        if not original_path:
            return {"success": False, "error": "Destination database path is missing in connection configuration."}

        snapshot_path = snap["path"]
        if not os.path.exists(snapshot_path):
            return {"success": False, "error": "Source snapshot database file is missing on disk."}

        try:
            # Overwrite the live database with the snapshot copy
            shutil.copy2(snapshot_path, original_path)
            return {"success": True, "message": f"Successfully rolled back live database to checkpoint: '{snap.get('label')}'."}
        except Exception as e:
            return {"success": False, "error": f"Failed to restore snapshot: {str(e)}"}
