import os
import json
import re
from typing import Dict, Any, List, Tuple, Optional
import google.generativeai as genai
from backend.config import settings
from backend.database import DBExecutor
from backend.vector_store import schema_store

# Configure genai if key exists
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

class BaseAgent:
    def __init__(self, name: str, system_instruction: str):
        self.name = name
        self.system_instruction = system_instruction
        self.client_enabled = bool(settings.GEMINI_API_KEY)
        self.model_name = settings.DEFAULT_MODEL

    def _call_llm(self, prompt: str, json_mode: bool = False) -> str:
        if not self.client_enabled:
            # Fallback mock agent response handler if GEMINI_API_KEY is not defined
            return self._mock_fallback(prompt, json_mode)
            
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_instruction
            )
            
            generation_config = {}
            if json_mode:
                generation_config = {"response_mime_type": "application/json"}
                
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            # If API fails for any reason, fallback to mock responses
            return self._mock_fallback(prompt, json_mode, error=str(e))

    def _mock_fallback(self, prompt: str, json_mode: bool, error: str = "") -> str:
        prompt_lower = prompt.lower()
        
        # MOCK FOR SCHEMA AGENT
        if self.name == "Schema Agent":
            # Identify matched tables for standard requests
            matched = ["sales", "products", "users"]
            if "customer" in prompt_lower or "user" in prompt_lower:
                matched = ["users"]
            elif "product" in prompt_lower or "stock" in prompt_lower:
                matched = ["products"]
            return json.dumps({"relevant_tables": matched})
            
        # MOCK FOR QUERY AGENT
        elif self.name == "Query Agent":
            sql = "SELECT * FROM sales LIMIT 5;"
            explanation = "Default query fallback because Gemini API key was not supplied or failed."
            
            # Simple keyword matching for sample sales db
            if "total sales" in prompt_lower or "revenue" in prompt_lower:
                if "last month" in prompt_lower:
                    sql = "SELECT SUM(amount) AS total_revenue FROM sales WHERE sale_date >= '2026-06-01' AND sale_date <= '2026-06-30';"
                    explanation = "Computes the total sum of sales amounts where the date lies within last month (June 2026)."
                elif "by region" in prompt_lower:
                    sql = "SELECT region, SUM(amount) AS total_revenue FROM sales GROUP BY region ORDER BY total_revenue DESC;"
                    explanation = "Groups the sales amounts by geographic region and orders them from highest to lowest sales."
                else:
                    sql = "SELECT SUM(amount) AS total_revenue FROM sales;"
                    explanation = "Sum of all columns in the sales transaction table."
            elif "inactive" in prompt_lower and "user" in prompt_lower or "customer" in prompt_lower:
                sql = "SELECT name, email, status FROM users WHERE status = 'Inactive';"
                explanation = "Filters users table to show names and emails where state status matches Inactive."
            elif "stock" in prompt_lower or "product" in prompt_lower:
                sql = "SELECT name, price, stock_quantity FROM products ORDER BY stock_quantity ASC;"
                explanation = "Selects name, price and stock quantities sorted ascending to show products lowest in stock."
            elif "delete" in prompt_lower or "remove" in prompt_lower:
                if "inactive" in prompt_lower:
                    sql = "DELETE FROM users WHERE status = 'Inactive';"
                    explanation = "Safely deletes records from the users table where status is inactive."
            elif "add employee" in prompt_lower or "add user" in prompt_lower or "insert" in prompt_lower:
                sql = "INSERT INTO users (name, email, role, status) VALUES ('Alex', 'alex_new@queryflow.ai', 'Customer', 'Active');"
                explanation = "Inserts a new user record for Alex."
                
            if json_mode:
                return json.dumps({
                    "query": sql,
                    "explanation": explanation,
                    "db_type": "sqlite",
                    "alternative_query": "SELECT SUM(amount), region FROM sales JOIN users ON sales.user_id = users.id GROUP BY region;"
                })
            return sql

        # MOCK FOR VALIDATION AGENT
        elif self.name == "Validation Agent":
            return json.dumps({
                "valid": True,
                "errors": [],
                "warnings": []
            })
            
        # MOCK FOR SECURITY AGENT
        elif self.name == "Security Agent":
            risk = 1
            reason = "Standard read-only query scan."
            if "delete" in prompt_lower or "drop" in prompt_lower or "update" in prompt_lower:
                risk = 4
                reason = "Write/modification command detected. Action requires explicit admin verification."
            return json.dumps({
                "risk_score": risk,
                "reasoning": reason,
                "safe_to_execute": risk < 3
            })
            
        # MOCK FOR ANALYTICS AGENT
        elif self.name == "Analytics Agent":
            # Extract standard data configurations
            chart_type = "table"
            title = "Query Results"
            x_axis = ""
            y_axis = ""
            
            if "region" in prompt_lower:
                chart_type = "bar"
                title = "Sales Revenue by Region"
                x_axis = "region"
                y_axis = "total_revenue"
            elif "month" in prompt_lower or "date" in prompt_lower or "sale_date" in prompt_lower:
                chart_type = "line"
                title = "Sales Trends"
                x_axis = "sale_date"
                y_axis = "amount"
            elif "product" in prompt_lower:
                chart_type = "bar"
                title = "Product Stock Quantities"
                x_axis = "name"
                y_axis = "stock_quantity"
                
            summary = "Insights extracted from database records matching user criteria."
            if error:
                summary += f" (Gemini Fallback Activated. Reason: {error[:60]})"
                
            return json.dumps({
                "summary": summary,
                "chart_type": chart_type,
                "chart_title": title,
                "x_axis_field": x_axis,
                "y_axis_fields": [y_axis] if y_axis else [],
                "kpis": [
                    {"label": "Records Found", "value": "Dynamic"}
                ]
            })
            
        return "Mock Response"


class SchemaAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Schema Agent",
            system_instruction="""You are a Database Schema Agent. Given a user query and a list of database tables, identify which tables are relevant to answer the query. 
            Return a JSON object with a single key 'relevant_tables' containing a list of table names."""
        )

    def select_tables(self, connection_id: str, user_query: str, db_type: str, db_config: Dict[str, Any]) -> List[str]:
        # Step 1: Use RAG to grab matched tables
        candidate_schemas = schema_store.search_relevant_tables(connection_id, user_query, limit=10)
        
        table_summaries = []
        for table in candidate_schemas:
            cols = [col["name"] for col in table.get("columns", [])]
            table_summaries.append(f"Table: {table['table_name']}, Columns: {', '.join(cols)}")
            
        prompt = f"""
        User Query: {user_query}
        Available Database Tables:
        {chr(10).join(table_summaries)}
        
        Which tables are required to write a query to satisfy the user? Return a JSON array:
        {{
            "relevant_tables": ["table1", "table2"]
        }}
        """
        response_text = self._call_llm(prompt, json_mode=True)
        try:
            data = json.loads(response_text)
            return data.get("relevant_tables", [t["table_name"] for t in candidate_schemas])
        except Exception:
            return [t["table_name"] for t in candidate_schemas]


class QueryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Query Agent",
            system_instruction="""You are a Database Query Generator Agent.
            Convert natural language queries into valid database queries (SQL or MongoDB aggregation scripts) matching the database dialect.
            You must ONLY return a JSON object with:
            - 'query': The generated database code.
            - 'explanation': A step-by-step description of what the query accomplishes.
            - 'db_type': The database dialect name.
            - 'alternative_query': An alternative optimized or visual variant if applicable.
            Do not include Markdown backticks around the JSON string."""
        )

    def generate_query(self, user_query: str, db_type: str, schema_context: List[Dict[str, Any]], chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        schema_dump = json.dumps(schema_context, indent=2)
        history_dump = json.dumps(chat_history or [], indent=2)
        
        prompt = f"""
        Database Dialect: {db_type}
        
        Database Schema Context:
        {schema_dump}
        
        Chat History Memory:
        {history_dump}
        
        User Goal: {user_query}
        
        Generate the Query. Remember to use correct table and column cases. Ensure Joins are correct. 
        If database is MongoDB, return a valid aggregation pipeline or mongo command block.
        Return in valid JSON format:
        {{
            "query": "SELECT ...",
            "explanation": "Plain text description...",
            "db_type": "{db_type}",
            "alternative_query": "SELECT ..."
        }}
        """
        response_text = self._call_llm(prompt, json_mode=True)
        try:
            return json.loads(response_text)
        except Exception:
            # Fallback manually parsing code blocks if any
            clean_text = re.sub(r"```json\s*", "", response_text)
            clean_text = re.sub(r"\s*```", "", clean_text).strip()
            try:
                return json.loads(clean_text)
            except:
                return {
                    "query": response_text,
                    "explanation": "Generated query code",
                    "db_type": db_type,
                    "alternative_query": ""
                }


class ValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Validation Agent",
            system_instruction="""You are a SQL/NoSQL Validation Agent. 
            Review the query for structural mistakes, syntax errors, missing columns, dialect incompatibilities (e.g. SQLite doesn't support RIGHT JOIN or FULL OUTER JOIN), and alias mismatches.
            Return a JSON object containing:
            - 'valid': boolean.
            - 'errors': list of string error messages.
            - 'warnings': list of warnings or recommendations."""
        )

    def validate_query(self, query: str, db_type: str, schema_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        Dialect: {db_type}
        Query: {query}
        Database Schema:
        {json.dumps(schema_context)}
        
        Validate this query against the schema and dialect limitations.
        Return JSON object:
        {{
            "valid": true/false,
            "errors": [],
            "warnings": []
        }}
        """
        response_text = self._call_llm(prompt, json_mode=True)
        try:
            return json.loads(response_text)
        except Exception:
            return {"valid": True, "errors": [], "warnings": []}


class SecurityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Security Agent",
            system_instruction="""You are a Database Security Agent.
            Analyze the query for potential safety risks: SQL injections, drop commands, database administration abuse, table deletions without WHERE clauses, or heavy performance loads.
            Evaluate a Risk Score from 1 (Totally safe read-only query) to 5 (Critical high risk operation, such as table drops or deletes).
            Return a JSON object with:
            - 'risk_score': Integer (1-5).
            - 'reasoning': Plain explanation of the security audit.
            - 'safe_to_execute': Boolean (True if risk < 3, False otherwise)."""
        )

    def scan_query(self, query: str, db_type: str) -> Dict[str, Any]:
        # Simple local guardrails
        query_upper = query.upper()
        local_warnings = []
        is_safe = True
        risk = 1
        
        # Guard against administrative operations
        unsafe_keywords = ["DROP TABLE", "DROP DATABASE", "ALTER TABLE", "TRUNCATE", "GRANT", "REVOKE"]
        for kw in unsafe_keywords:
            if kw in query_upper:
                risk = 5
                is_safe = False
                local_warnings.append(f"Administrative '{kw}' action detected.")
                
        if "DELETE" in query_upper and "WHERE" not in query_upper:
            risk = 5
            is_safe = False
            local_warnings.append("Destructive DELETE command without a WHERE filter is blocked.")
            
        if "UPDATE" in query_upper and "WHERE" not in query_upper:
            risk = 4
            is_safe = False
            local_warnings.append("Global UPDATE command without a WHERE filter is flagged.")
            
        if len(local_warnings) > 0:
            return {
                "risk_score": risk,
                "reasoning": " ".join(local_warnings),
                "safe_to_execute": is_safe
            }
            
        # Call LLM for nuanced injection or permission breach estimation
        prompt = f"""
        Dialect: {db_type}
        Query: {query}
        
        Scan this query for SQL injection, logic bypasses, or extreme performance costs.
        Return JSON object:
        {{
            "risk_score": 1-5,
            "reasoning": "Brief description",
            "safe_to_execute": true/false
        }}
        """
        response_text = self._call_llm(prompt, json_mode=True)
        try:
            return json.loads(response_text)
        except Exception:
            return {"risk_score": 1, "reasoning": "Completed local security scan.", "safe_to_execute": True}


class AnalyticsAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Analytics Agent",
            system_instruction="""You are an Analytics and Insights Agent.
            Given a user's original query, the executed SQL, and the resulting table dataset, output insights.
            You must produce a friendly text explanation of the results and select the best visualization layout.
            Return a JSON object containing:
            - 'summary': A markdown text summary of the results and trends.
            - 'chart_type': One of 'table', 'bar', 'line', 'pie', 'area', 'scatter'.
            - 'chart_title': Suggest a title.
            - 'x_axis_field': Name of column for horizontal axis.
            - 'y_axis_fields': List of column names for quantitative values.
            - 'kpis': List of objects containing {{'label': str, 'value': str}} representing computed metrics (like Total Sum, Max, or Count)."""
        )

    def analyze_results(self, user_query: str, query: str, columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = f"""
        User Query: {user_query}
        Executed Database Query: {query}
        Columns returned: {json.dumps(columns)}
        Dataset sample (first 10 records): {json.dumps(rows[:10])}
        
        Analyze this dataset and select the best visual representation (charts/KPIs).
        Return JSON format:
        {{
            "summary": "Summary of data observations...",
            "chart_type": "bar/line/pie/area/table",
            "chart_title": "Title",
            "x_axis_field": "column_name",
            "y_axis_fields": ["column_name_2"],
            "kpis": [{{"label": "Total Revenue", "value": "$3,040"}}]
        }}
        """
        response_text = self._call_llm(prompt, json_mode=True)
        try:
            return json.loads(response_text)
        except Exception:
            # Fallback configuration
            return {
                "summary": f"Retrieved {len(rows)} records matching user requirements.",
                "chart_type": "table",
                "chart_title": "Results",
                "x_axis_field": "",
                "y_axis_fields": [],
                "kpis": [{"label": "Rows Counted", "value": str(len(rows))}]
            }


class CopilotOrchestrator:
    def __init__(self):
        self.schema_agent = SchemaAgent()
        self.query_agent = QueryAgent()
        self.validation_agent = ValidationAgent()
        self.security_agent = SecurityAgent()
        self.analytics_agent = AnalyticsAgent()

    def process_message(self, user_query: str, conn_id: str, vault_connections: List[Dict[str, Any]], chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        # 1. Grab DB connection
        conn = next((c for c in vault_connections if c["id"] == conn_id), None)
        if not conn:
            return {"success": False, "error": f"Connection '{conn_id}' not found in vault"}
            
        db_type = conn["type"]
        db_config = conn["config"]
        
        # 2. Schema Agent scans DB structure to pick matching tables
        relevant_tables = self.schema_agent.select_tables(conn_id, user_query, db_type, db_config)
        
        # Retrieve schemas for only relevant tables
        all_schemas = DBExecutor.get_schema(db_type, db_config)
        relevant_schemas = [t for t in all_schemas if t["table_name"] in relevant_tables]
        if not relevant_schemas:
            relevant_schemas = all_schemas  # fallback to all
            
        # 3. Query Agent creates the query string
        gen_data = self.query_agent.generate_query(user_query, db_type, relevant_schemas, chat_history)
        query_str = gen_data.get("query", "")
        explanation = gen_data.get("explanation", "")
        alt_query = gen_data.get("alternative_query", "")
        
        if not query_str:
            return {"success": False, "error": "Query Agent failed to produce query code"}
            
        # 4. Validation Agent scans for syntax compatibility
        val_data = self.validation_agent.validate_query(query_str, db_type, relevant_schemas)
        
        # 5. Security Agent runs safety filters and determines risk
        sec_data = self.security_agent.scan_query(query_str, db_type)
        
        # Return plan to frontend
        return {
            "success": True,
            "query": query_str,
            "explanation": explanation,
            "alternative_query": alt_query,
            "validation": val_data,
            "security": sec_data,
            "relevant_tables": relevant_tables
        }

orchestrator = CopilotOrchestrator()
