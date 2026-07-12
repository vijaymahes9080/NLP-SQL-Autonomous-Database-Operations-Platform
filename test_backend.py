import os
import json
import unittest
from backend.database import ConnectionVault, DBExecutor, encrypt_data, decrypt_data
from backend.vector_store import schema_store
from backend.security_sandbox import SecuritySandbox
from backend.agents import orchestrator

class TestQueryFlowBackend(unittest.TestCase):
    def setUp(self):
        # Setup temporary directories/files if needed
        pass

    def test_01_encryption(self):
        secret = "postgres://admin:super_secret@host:5432/db"
        encrypted = encrypt_data(secret)
        self.assertNotEqual(secret, encrypted)
        
        decrypted = decrypt_data(encrypted)
        self.assertEqual(secret, decrypted)
        print("[OK] Credentials Vault Encryption Verified.")

    def test_02_connection_vault(self):
        vault = ConnectionVault()
        conns = vault.get_connections()
        
        # We should have the default sample SQLite connection
        self.assertTrue(len(conns) > 0)
        self.assertEqual(conns[0]["id"], "sample_sqlite")
        self.assertEqual(conns[0]["type"], "sqlite")
        print("[OK] Connection Vault Retrieval Verified.")

    def test_03_database_executor_sqlite(self):
        conns = ConnectionVault().get_connections()
        sample_config = conns[0]["config"]
        
        # Test schema retrieval
        schema = DBExecutor.get_schema("sqlite", sample_config)
        self.assertTrue(len(schema) > 0)
        
        # Check if users table is present
        table_names = [t["table_name"] for t in schema]
        self.assertIn("users", table_names)
        self.assertIn("products", table_names)
        self.assertIn("sales", table_names)
        
        # Execute query
        res = DBExecutor.execute_query("sqlite", sample_config, "SELECT COUNT(*) AS total FROM users;")
        self.assertTrue(res["success"])
        self.assertEqual(res["rows"][0]["total"], 7) # We inserted 7 mock users
        print("[OK] Database Schema Extraction & Query Run Verified.")

    def test_04_schema_fts_rag(self):
        conns = ConnectionVault().get_connections()
        sample_config = conns[0]["config"]
        schema = DBExecutor.get_schema("sqlite", sample_config)
        
        # Index schema
        schema_store.index_database_schema("sample_sqlite", schema)
        
        # Query matching tables
        matched = schema_store.search_relevant_tables("sample_sqlite", "sales region revenue")
        matched_names = [m["table_name"] for m in matched]
        self.assertIn("sales", matched_names)
        print("[OK] Hybrid FAG Schema Retrieval System Verified.")

    def test_05_security_sandbox(self):
        conns = ConnectionVault().get_connections()
        sample_config = conns[0]["config"]
        
        # 1. READ queries should execute in SAFE mode
        res_read = SecuritySandbox.execute_with_sandbox("sqlite", sample_config, "SELECT name FROM users LIMIT 1;", "SAFE")
        self.assertTrue(res_read["success"])
        
        # 2. WRITE queries should fail in SAFE mode
        res_write_blocked = SecuritySandbox.execute_with_sandbox("sqlite", sample_config, "DELETE FROM users WHERE id = 999;", "SAFE")
        self.assertFalse(res_write_blocked["success"])
        self.assertIn("Blocked", res_write_blocked["error"])
        
        # 3. WRITE queries in SANDBOX mode should clone database, execute simulated changes, and NOT mutate original DB
        # Count users
        count_before = DBExecutor.execute_query("sqlite", sample_config, "SELECT COUNT(*) as c FROM users;")["rows"][0]["c"]
        
        # Run deletion inside sandbox replica
        res_sandbox = SecuritySandbox.execute_with_sandbox(
            "sqlite", sample_config, "DELETE FROM users WHERE email = 'sarah@gmail.com';", "SANDBOX"
        )
        self.assertTrue(res_sandbox["success"])
        self.assertTrue(res_sandbox["sandbox_simulated"])
        self.assertEqual(res_sandbox["rows_affected"], 1)
        
        # Verify original DB count is unchanged
        count_after = DBExecutor.execute_query("sqlite", sample_config, "SELECT COUNT(*) as c FROM users;")["rows"][0]["c"]
        self.assertEqual(count_before, count_after)
        print("[OK] Security Sandbox (SAFE/SANDBOX Modes) Verified.")

    def test_06_agents_copilot(self):
        conns = ConnectionVault().get_connections()
        
        # Orchestrate complete message flow
        res = orchestrator.process_message(
            user_query="Show total sales amount",
            conn_id="sample_sqlite",
            vault_connections=conns
        )
        
        self.assertTrue(res["success"])
        self.assertIn("query", res)
        self.assertIn("explanation", res)
        self.assertTrue(res["security"]["safe_to_execute"])
        print("[OK] Multi-Agent Orchestrator Pipeline Verified.")

if __name__ == "__main__":
    unittest.main()
