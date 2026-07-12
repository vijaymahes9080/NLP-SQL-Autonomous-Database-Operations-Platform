import os
import json
import csv
import sqlite3
import io
from typing import Dict, Any, List, Tuple
from backend.config import settings
from backend.database import DBExecutor, vault
from backend.agents import BaseAgent

class ETLAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ETL Agent",
            system_instruction="""You are a Data Ingestion & ETL Agent.
            Analyze raw data samples (which could be unstructured text, logs, CSV snippets, or JSON records).
            Infer a clean relational database schema (table name, column names, column types) that can represent this data.
            Generate the SQLite DDL statement to create this table.
            You must ONLY return a JSON object with:
            - 'table_name': A clean, lowercase snake_case table name.
            - 'columns': An array of objects, each with 'name' (snake_case column name) and 'type' (e.g. TEXT, REAL, INTEGER).
            - 'create_table_sql': The CREATE TABLE statement.
            Do not include Markdown backticks around the JSON string."""
        )

    def infer_schema(self, raw_sample: str, proposed_table_name: str) -> Dict[str, Any]:
        prompt = f"""
        Proposed Table Name: {proposed_table_name}
        
        Raw Data Sample (first few records/lines):
        {raw_sample}
        
        Infer the schema and generate the DDL script. Return in valid JSON format:
        {{
            "table_name": "...",
            "columns": [
                {{"name": "col1", "type": "TEXT"}},
                {{"name": "col2", "type": "INTEGER"}}
            ],
            "create_table_sql": "CREATE TABLE IF NOT EXISTS ..."
        }}
        """
        response_text = self._call_llm(prompt, json_mode=True)
        try:
            return json.loads(response_text)
        except Exception:
            # Fallback parser
            import re
            clean_text = re.sub(r"```json\s*", "", response_text)
            clean_text = re.sub(r"\s*```", "", clean_text).strip()
            try:
                return json.loads(clean_text)
            except Exception:
                # Basic mock fallback schema
                return {
                    "table_name": proposed_table_name.lower().replace(" ", "_"),
                    "columns": [
                        {"name": "id", "type": "INTEGER PRIMARY KEY AUTOINCREMENT"},
                        {"name": "raw_content", "type": "TEXT"},
                        {"name": "metadata", "type": "TEXT"}
                    ],
                    "create_table_sql": f"CREATE TABLE IF NOT EXISTS {proposed_table_name.lower().replace(' ', '_')} (id INTEGER PRIMARY KEY AUTOINCREMENT, raw_content TEXT, metadata TEXT);"
                }

    def parse_unstructured_data(self, raw_content: str, target_columns: List[str]) -> List[Dict[str, Any]]:
        """
        Uses Gemini to parse unstructured paragraphs or logs into clean structured lists matching target columns.
        """
        parsing_agent = BaseAgent(
            name="ETL Parsing Subagent",
            system_instruction="""You are a data parsing assistant.
            Extract details from the raw unstructured text, logs, or reports.
            Structure the data into a JSON array of records. Each record must be a JSON object containing keys that match the specified target columns.
            Return ONLY a valid JSON array of objects. Do not include markdown wraps."""
        )
        
        prompt = f"""
        Target Columns to Extract: {', '.join(target_columns)}
        
        Raw Text Content:
        {raw_content[:4000]} # Limit to protect token window
        
        Extract records and return as a JSON array of objects:
        [
            { {col: "value" for col in target_columns} }
        ]
        """
        response_text = parsing_agent._call_llm(prompt, json_mode=True)
        try:
            return json.loads(response_text)
        except Exception:
            # Fallback: single record
            return [{col: "Parsing Fallback Value" for col in target_columns}]


class ETLPipelineBuilder:
    @classmethod
    def ingest_data(cls, conn_id: str, db_type: str, config: Dict[str, Any], table_name: str, raw_content: str) -> Dict[str, Any]:
        if db_type != "sqlite":
            return {"success": False, "error": "ETL Ingestion is currently only supported for local SQLite databases."}

        db_path = config.get("database_path", "")
        if not db_path or not os.path.exists(db_path):
            return {"success": False, "error": "Database path is missing or invalid."}

        # 1. Take a sample for schema inference
        sample_size = 1000
        raw_sample = raw_content[:sample_size]
        
        agent = ETLAgent()
        inferred = agent.infer_schema(raw_sample, table_name)
        
        final_table_name = inferred.get("table_name", table_name.lower().replace(" ", "_"))
        columns = inferred.get("columns", [])
        create_sql = inferred.get("create_table_sql", "")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # 2. Check if table already exists (Schema Drift detection)
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{final_table_name}';")
            table_exists = cursor.fetchone()

            drift_actions = []
            if not table_exists:
                # Run creation DDL
                cursor.execute(create_sql)
                conn.commit()
                drift_actions.append(f"Created table '{final_table_name}' using inferred DDL.")
            else:
                # Detect and resolve schema drift: add any columns in data not in database
                cursor.execute(f"PRAGMA table_info('{final_table_name}');")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                for col in columns:
                    col_name = col["name"]
                    # Ignore case issues or id primary keys
                    if col_name.lower() not in [c.lower() for c in existing_columns] and col_name.lower() != "id":
                        col_type = col.get("type", "TEXT")
                        # Alter Table to add missing column
                        cursor.execute(f"ALTER TABLE {final_table_name} ADD COLUMN {col_name} {col_type};")
                        drift_actions.append(f"Resolved Schema Drift: Added column '{col_name}' ({col_type}) to table '{final_table_name}'.")
                conn.commit()

            # 3. Parse content (JSON, CSV, or Unstructured)
            records = []
            raw_stripped = raw_content.strip()
            
            # Check JSON
            if (raw_stripped.startswith("[") and raw_stripped.endswith("]")) or (raw_stripped.startswith("{") and raw_stripped.endswith("}")):
                try:
                    parsed_json = json.loads(raw_stripped)
                    if isinstance(parsed_json, list):
                        records = parsed_json
                    else:
                        records = [parsed_json]
                except Exception:
                    pass

            # Check CSV if JSON parsing was not triggered
            if not records:
                try:
                    # Very basic check: look for commas or tabs
                    if "," in raw_sample or "\t" in raw_sample:
                        csv_file = io.StringIO(raw_content)
                        reader = csv.DictReader(csv_file)
                        records = [dict(row) for row in reader]
                except Exception:
                    pass

            # Fallback to LLM Unstructured Parser
            if not records:
                target_col_names = [col["name"] for col in columns if col["name"] != "id"]
                records = agent.parse_unstructured_data(raw_content, target_col_names)

            # 4. Insert records
            if not records:
                return {"success": False, "error": "Unable to parse data into records for insertion."}

            # Fetch refreshed table columns
            cursor.execute(f"PRAGMA table_info('{final_table_name}');")
            db_cols = [row[1] for row in cursor.fetchall()]
            db_cols_filtered = [c for c in db_cols if c.lower() != "id"]

            inserted_count = 0
            for record in records:
                # Align values with table columns
                val_placeholder = ", ".join(["?" for _ in db_cols_filtered])
                col_names_str = ", ".join(db_cols_filtered)
                
                # Fetch matching value, default to None if missing
                values = []
                for col in db_cols_filtered:
                    # Match key case-insensitively
                    val = None
                    for k, v in record.items():
                        if k.lower() == col.lower():
                            val = v
                            break
                    values.append(val)
                
                insert_sql = f"INSERT INTO {final_table_name} ({col_names_str}) VALUES ({val_placeholder});"
                cursor.execute(insert_sql, values)
                inserted_count += 1

            conn.commit()
            conn.close()

            # Refresh table schema in local index
            try:
                schema = DBExecutor.get_schema("sqlite", config)
                from backend.vector_store import schema_store
                schema_store.index_database_schema(conn_id, schema)
            except Exception:
                pass

            return {
                "success": True,
                "table_name": final_table_name,
                "columns": db_cols,
                "rows_inserted": inserted_count,
                "drift_actions": drift_actions,
                "message": f"Successfully ingested {inserted_count} records into table '{final_table_name}'."
            }

        except Exception as e:
            conn.rollback()
            conn.close()
            return {"success": False, "error": f"ETL Pipeline execution error: {str(e)}"}
