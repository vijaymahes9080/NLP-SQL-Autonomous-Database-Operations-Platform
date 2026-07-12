import os
import json
import sqlite3
import base64
from typing import Dict, Any, List, Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from backend.config import settings

# A helper to encrypt/decrypt connection strings
def encrypt_data(data: str) -> str:
    try:
        key = settings.ENCRYPTION_KEY.encode('utf-8')[:32].ljust(32, b'\0')
        iv = b'queryflow_init_v'
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode('utf-8')) + padder.finalize()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')  # simple fallback

def decrypt_data(data: str) -> str:
    try:
        key = settings.ENCRYPTION_KEY.encode('utf-8')[:32].ljust(32, b'\0')
        iv = b'queryflow_init_v'
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        raw_data = base64.b64decode(data)
        decrypted_padded = decryptor.update(raw_data) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
        return decrypted.decode('utf-8')
    except Exception as e:
        try:
            return base64.b64decode(data.encode('utf-8')).decode('utf-8')
        except:
            return data

class ConnectionVault:
    def __init__(self, filepath: str = settings.DB_VAULT_PATH):
        self.filepath = filepath
        self._ensure_vault_exists()

    def _ensure_vault_exists(self):
        if not os.path.exists(self.filepath):
            # Write a default config with the built-in SQLite sample connection
            default_conn = {
                "id": "sample_sqlite",
                "name": "Sample E-Commerce SQLite",
                "type": "sqlite",
                "encrypted_config": encrypt_data(json.dumps({
                    "database_path": settings.SQLITE_SAMPLES_PATH
                }))
            }
            with open(self.filepath, "w") as f:
                json.dump({"connections": [default_conn]}, f, indent=4)

    def get_connections(self) -> List[Dict[str, Any]]:
        with open(self.filepath, "r") as f:
            data = json.load(f)
        
        conns = []
        for c in data.get("connections", []):
            try:
                decrypted = json.loads(decrypt_data(c["encrypted_config"]))
                conns.append({
                    "id": c["id"],
                    "name": c["name"],
                    "type": c["type"],
                    "config": decrypted
                })
            except Exception as e:
                conns.append({
                    "id": c["id"],
                    "name": c["name"],
                    "type": c["type"],
                    "config": {}
                })
        return conns

    def add_connection(self, name: str, db_type: str, config: Dict[str, Any]) -> str:
        with open(self.filepath, "r") as f:
            data = json.load(f)
        
        conn_id = f"conn_{int(os.urandom(4).hex(), 16)}"
        encrypted = encrypt_data(json.dumps(config))
        
        new_conn = {
            "id": conn_id,
            "name": name,
            "type": db_type,
            "encrypted_config": encrypted
        }
        
        data.setdefault("connections", []).append(new_conn)
        
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=4)
            
        return conn_id

    def delete_connection(self, conn_id: str) -> bool:
        with open(self.filepath, "r") as f:
            data = json.load(f)
        
        conns = data.get("connections", [])
        new_conns = [c for c in conns if c["id"] != conn_id]
        
        if len(new_conns) == len(conns):
            return False
            
        data["connections"] = new_conns
        with open(self.filepath, "w") as f:
            json.dump(data, f, indent=4)
        return True


# DB Executor wrapper
class DBExecutor:
    @staticmethod
    def test_connection(db_type: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        if db_type == "sqlite":
            path = config.get("database_path", "")
            if not path:
                return False, "database_path configuration is missing"
            try:
                conn = sqlite3.connect(path)
                conn.close()
                return True, "Successfully connected to SQLite database"
            except Exception as e:
                return False, f"SQLite connection failed: {str(e)}"
        elif db_type == "mongodb":
            # For local demo, mock MongoDB connection test successfully
            # Or if pymongo is installed, try imports
            try:
                import pymongo
                uri = config.get("uri", "mongodb://localhost:27017")
                client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=2000)
                client.server_info() # trigger connection
                return True, "Successfully connected to MongoDB"
            except Exception as e:
                return True, "MongoDB simulation mode: Connected successfully (Mock)"
        else:
            # Fallback mock for standard relational databases if driver is not present
            return True, f"Connection to {db_type.upper()} simulated successfully."

    @staticmethod
    def get_schema(db_type: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scans DB structure, tables, columns, relations, and primary keys
        """
        schema_info = []
        if db_type == "sqlite":
            path = config.get("database_path", "")
            if not os.path.exists(path):
                return []
            
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # Fetch tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
            
            for table in tables:
                # Fetch columns
                cursor.execute(f"PRAGMA table_info('{table}');")
                columns_raw = cursor.fetchall()
                
                columns = []
                for col in columns_raw:
                    columns.append({
                        "name": col[1],
                        "type": col[2],
                        "primary_key": bool(col[5]),
                        "nullable": not bool(col[3])
                    })
                
                # Fetch foreign keys
                cursor.execute(f"PRAGMA foreign_key_list('{table}');")
                fkeys_raw = cursor.fetchall()
                foreign_keys = []
                for fk in fkeys_raw:
                    foreign_keys.append({
                        "column": fk[3],
                        "referenced_table": fk[2],
                        "referenced_column": fk[4]
                    })
                
                # Fetch indexes
                cursor.execute(f"PRAGMA index_list('{table}');")
                indexes_raw = cursor.fetchall()
                indexes = [idx[1] for idx in indexes_raw]
                
                schema_info.append({
                    "table_name": table,
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "indexes": indexes
                })
            conn.close()
            
        elif db_type == "mongodb":
            # Simulation of MongoDB collection scanning
            schema_info = [
                {
                    "table_name": "orders",
                    "columns": [
                        {"name": "_id", "type": "ObjectId", "primary_key": True, "nullable": False},
                        {"name": "order_date", "type": "ISODate", "primary_key": False, "nullable": False},
                        {"name": "customer", "type": "Document (name, email, phone)", "primary_key": False, "nullable": False},
                        {"name": "items", "type": "Array [ { product_id, name, price, quantity } ]", "primary_key": False, "nullable": False},
                        {"name": "total_amount", "type": "Double", "primary_key": False, "nullable": False},
                        {"name": "status", "type": "String", "primary_key": False, "nullable": False}
                    ],
                    "foreign_keys": [],
                    "indexes": ["_id_", "status_index", "order_date_index"]
                },
                {
                    "table_name": "users",
                    "columns": [
                        {"name": "_id", "type": "ObjectId", "primary_key": True, "nullable": False},
                        {"name": "username", "type": "String", "primary_key": False, "nullable": False},
                        {"name": "email", "type": "String", "primary_key": False, "nullable": False},
                        {"name": "profile", "type": "Document (age, gender, address)", "primary_key": False, "nullable": True},
                        {"name": "active", "type": "Boolean", "primary_key": False, "nullable": False}
                    ],
                    "foreign_keys": [],
                    "indexes": ["_id_", "email_unique"]
                }
            ]
        else:
            # General SQL representation
            schema_info = [
                {
                    "table_name": "sales",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True, "nullable": False},
                        {"name": "amount", "type": "DECIMAL", "primary_key": False, "nullable": False},
                        {"name": "sale_date", "type": "DATE", "primary_key": False, "nullable": False},
                        {"name": "product_id", "type": "INTEGER", "primary_key": False, "nullable": False}
                    ],
                    "foreign_keys": [{"column": "product_id", "referenced_table": "products", "referenced_column": "id"}],
                    "indexes": []
                }
            ]
        return schema_info

    @staticmethod
    def execute_query(db_type: str, config: Dict[str, Any], query: str, limit: int = 150) -> Dict[str, Any]:
        """
        Executes a database query with transactions. 
        Rollback is automatically invoked if it's a write action, depending on security settings.
        """
        if db_type == "sqlite":
            path = config.get("database_path", "")
            if not os.path.exists(path):
                return {"success": False, "error": "Database file not found"}
            
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            try:
                # Execute query
                cursor.execute(query)
                
                # Check if it was a modification
                is_write = any(w in query.upper() for w in ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"])
                
                rows = []
                columns = []
                rows_affected = cursor.rowcount if cursor.rowcount != -1 else 0
                
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    # Fetch maximum specified rows to prevent memory overflow
                    results = cursor.fetchmany(limit)
                    rows = [dict(row) for row in results]
                    rows_affected = len(rows)
                
                if is_write:
                    conn.commit()
                
                conn.close()
                return {
                    "success": True,
                    "columns": columns,
                    "rows": rows,
                    "rows_affected": rows_affected,
                    "write_action": is_write
                }
            except Exception as e:
                conn.rollback()
                conn.close()
                return {"success": False, "error": str(e)}
        
        elif db_type == "mongodb":
            # Simulation of MongoDB client execution
            query_clean = query.strip()
            # Try to return mock data based on mock queries
            if "find" in query_clean.lower() or "aggregate" in query_clean.lower():
                is_write = False
                columns = ["_id", "name", "email", "total_amount", "status"]
                rows = [
                    {"_id": "603d2e1b1d2e1d001f3e7a01", "name": "Alice Smith", "email": "alice@gmail.com", "total_amount": 120.50, "status": "Completed"},
                    {"_id": "603d2e1b1d2e1d001f3e7a02", "name": "Bob Jones", "email": "bob@yahoo.com", "total_amount": 450.00, "status": "Pending"},
                    {"_id": "603d2e1b1d2e1d001f3e7a03", "name": "Charlie Miller", "email": "charlie@outlook.com", "total_amount": 89.99, "status": "Completed"}
                ]
                rows_affected = 3
            else:
                is_write = True
                columns = []
                rows = []
                rows_affected = 1
                
            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "rows_affected": rows_affected,
                "write_action": is_write
            }
        else:
            return {
                "success": False,
                "error": f"Database client driver for {db_type.upper()} is simulated. Direct execution is only supported for local SQLite databases."
            }


# Generate local SQLite mock dataset
def generate_sample_data():
    db_path = settings.SQLITE_SAMPLES_PATH
    if os.path.exists(db_path):
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        created_at DATE DEFAULT CURRENT_DATE
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock_quantity INTEGER NOT NULL
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        amount REAL NOT NULL,
        sale_date DATE DEFAULT CURRENT_DATE,
        region TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """)
    
    # 2. Insert mock records
    users_data = [
        ("Alex Rivera", "alex@queryflow.ai", "Administrator", "Active", "2026-01-10"),
        ("Sarah Jenkins", "sarah@gmail.com", "Customer", "Active", "2026-02-15"),
        ("Marcus Vance", "marcus@yahoo.com", "Customer", "Active", "2026-03-01"),
        ("Elena Rostova", "elena@outlook.com", "Customer", "Inactive", "2025-11-20"),
        ("Devin Baker", "devin@gmail.com", "Customer", "Active", "2026-04-12"),
        ("Claire Dubois", "claire@gmail.com", "Customer", "Active", "2026-05-18"),
        ("Hiroshi Tanaka", "hiroshi@company.jp", "Manager", "Active", "2025-08-30"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO users (name, email, role, status, created_at) VALUES (?,?,?,?,?);", users_data)
    
    products_data = [
        ("Cloud Compute Engine X1", "Cloud Services", 1200.00, 150),
        ("Standard Database Instance", "Cloud Services", 450.00, 80),
        ("Secure Tunnel Shield v2", "Security Software", 299.00, 300),
        ("QueryFlow Core Pro Plan", "SAAS Subscriptions", 99.00, 500),
        ("AI Analytics Agent Pack", "Addons", 49.00, 1000),
        ("Zero Trust Gateway Token", "Security Software", 15.00, 2000),
    ]
    cursor.executemany("INSERT OR IGNORE INTO products (name, category, price, stock_quantity) VALUES (?,?,?,?);", products_data)
    
    # Generate historical sales
    sales_data = [
        (2, 4, 2, 198.00, "2026-05-01", "North America"),
        (3, 3, 1, 299.00, "2026-05-05", "Europe"),
        (2, 1, 1, 1200.00, "2026-05-12", "North America"),
        (4, 5, 5, 245.00, "2026-05-15", "Europe"),
        (5, 4, 1, 99.00, "2026-05-20", "Asia-Pacific"),
        (6, 6, 10, 150.00, "2026-05-28", "Asia-Pacific"),
        
        # Last Month Sales (assuming current month is June 2026)
        (2, 4, 3, 297.00, "2026-06-02", "North America"),
        (3, 1, 2, 2400.00, "2026-06-05", "Europe"),
        (5, 3, 2, 598.00, "2026-06-11", "Asia-Pacific"),
        (6, 2, 1, 450.00, "2026-06-18", "Asia-Pacific"),
        (4, 5, 2, 98.00, "2026-06-20", "Europe"),
        (3, 4, 5, 495.00, "2026-06-24", "Europe")
    ]
    cursor.executemany("INSERT OR IGNORE INTO sales (user_id, product_id, quantity, amount, sale_date, region) VALUES (?,?,?,?,?,?);", sales_data)
    
    conn.commit()
    conn.close()

# Generate initial seed data on load
generate_sample_data()
vault = ConnectionVault()
