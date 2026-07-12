import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "QueryFlow AI"
    API_V1_STR: str = "/api/v1"
    
    # LLM configurations
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DEFAULT_MODEL: str = "gemini-1.5-flash"  # Highly performant, fast, and cost-effective
    
    # Security Configurations
    # Used for encrypting database connection credentials in the vault
    ENCRYPTION_KEY: str = os.getenv("QUERYFLOW_ENCRYPTION_KEY", "qF_default_secret_key_32_bytes_len!")
    
    # Safe execution configurations
    # Modes: "SAFE" (read-only), "APPROVAL" (requires human button click for write), "SANDBOX" (executes on ephemeral SQLite copy), "AUTONOMOUS" (full auto)
    DEFAULT_EXECUTION_MODE: str = "APPROVAL"
    
    # Storage settings
    WORKSPACE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    DB_VAULT_PATH: str = os.path.join(WORKSPACE_DIR, "db_vault.json")
    SQLITE_SAMPLES_PATH: str = os.path.join(WORKSPACE_DIR, "samples.db")
    VECTOR_DB_PATH: str = os.path.join(WORKSPACE_DIR, "schema_vectors.db")
    AUDIT_LOG_PATH: str = os.path.join(WORKSPACE_DIR, "audit_log.json")
    WORKFLOWS_PATH: str = os.path.join(WORKSPACE_DIR, "workflows.json")

settings = Settings()
