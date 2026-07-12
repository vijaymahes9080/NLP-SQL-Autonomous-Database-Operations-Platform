import os
import json
import sqlite3
from typing import List, Dict, Any
import google.generativeai as genai
from backend.config import settings

class SchemaVectorStore:
    def __init__(self, filepath: str = settings.VECTOR_DB_PATH):
        self.filepath = filepath
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()
        
        # Table to store raw schema details
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schemas (
            connection_id TEXT,
            table_name TEXT,
            schema_json TEXT,
            PRIMARY KEY (connection_id, table_name)
        );
        """)
        
        # SQLite FTS5 (Full Text Search) for schema indexing
        try:
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS schema_fts USING fts5(
                connection_id,
                table_name,
                columns,
                relations,
                tokenize="porter unicode61"
            );
            """)
        except Exception:
            # Fallback if FTS5 is not compiled in the system python sqlite3 wrapper
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_fts (
                connection_id TEXT,
                table_name TEXT,
                columns TEXT,
                relations TEXT
            );
            """)
            
        conn.commit()
        conn.close()

    def index_database_schema(self, connection_id: str, schema_info: List[Dict[str, Any]]):
        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()
        
        # Clear existing records for this connection
        cursor.execute("DELETE FROM schemas WHERE connection_id = ?;", (connection_id,))
        cursor.execute("DELETE FROM schema_fts WHERE connection_id = ?;", (connection_id,))
        
        for table in schema_info:
            table_name = table["table_name"]
            schema_json = json.dumps(table)
            
            # Format columns and types into a searchable block
            cols_text = ", ".join([f"{col['name']} ({col['type']})" for col in table.get("columns", [])])
            
            # Format foreign keys
            fk_text = ", ".join([f"{fk['column']} references {fk['referenced_table']}({fk['referenced_column']})" 
                                for fk in table.get("foreign_keys", [])])
            
            # Insert raw
            cursor.execute(
                "INSERT INTO schemas (connection_id, table_name, schema_json) VALUES (?, ?, ?);",
                (connection_id, table_name, schema_json)
            )
            
            # Insert searchable FTS
            cursor.execute(
                "INSERT INTO schema_fts (connection_id, table_name, columns, relations) VALUES (?, ?, ?, ?);",
                (connection_id, table_name, cols_text, fk_text)
            )
            
        conn.commit()
        conn.close()

    def search_relevant_tables(self, connection_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves matching table schemas using FTS search or fallback matching.
        """
        conn = sqlite3.connect(self.filepath)
        cursor = conn.cursor()
        
        # Check if we can do full text search
        try:
            # Rank based on BM25 match
            cursor.execute(
                """
                SELECT table_name FROM schema_fts 
                WHERE connection_id = ? AND schema_fts MATCH ? 
                LIMIT ?;
                """,
                (connection_id, f"{query}*", limit)
            )
            matched_tables = [row[0] for row in cursor.fetchall()]
        except Exception:
            # Fallback simple LIKE matching
            words = query.lower().split()
            matched_tables = []
            if words:
                like_clauses = " OR ".join(["columns LIKE ?" for _ in words])
                params = [connection_id] + [f"%{word}%" for word in words]
                cursor.execute(
                    f"SELECT table_name FROM schema_fts WHERE connection_id = ? AND ({like_clauses}) LIMIT ?;",
                    tuple(params + [limit])
                )
                matched_tables = [row[0] for row in cursor.fetchall()]
        
        # If no matches, pull all tables
        if not matched_tables:
            cursor.execute("SELECT table_name FROM schemas WHERE connection_id = ? LIMIT ?;", (connection_id, limit))
            matched_tables = [row[0] for row in cursor.fetchall()]
            
        # Retrieve the full JSON schema
        results = []
        for table_name in matched_tables:
            cursor.execute("SELECT schema_json FROM schemas WHERE connection_id = ? AND table_name = ?;", (connection_id, table_name))
            row = cursor.fetchone()
            if row:
                results.append(json.loads(row[0]))
                
        conn.close()
        return results

schema_store = SchemaVectorStore()
