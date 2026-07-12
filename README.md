# QueryFlow AI ⚡

QueryFlow AI is an enterprise-grade AI Database Operating System that translates natural language questions into database queries (SQL & MongoDB Aggregations), executes them safely within sandbox limits, analyzes the results, provides plain-language explanations, and displays dashboards.

It acts as a **ChatGPT + SQL IDE + Database Administrator + Analytics Dashboard + Agentic Workflow Scheduler** combined into a unified, secure system.

---

## ✨ Core Features

1. **Conversational Database Copilot**: Multi-turn chat interface that retains session context, answers follow-up questions, and explains queries in simple human language.
2. **Autonomous Agent Orchestrator**: Uses a multi-agent coordinate pipeline:
   - **Schema Agent + Hybrid RAG**: Dynamically identifies the minimum tables and columns needed using local Full-Text Search (FTS5).
   - **Query Agent**: Converts conversational intents to target dialects (SQLite, PostgreSQL, MySQL, MongoDB aggregates).
   - **Validation Agent**: Audits queries for syntax defects and dialect compatibilities.
   - **Security Agent**: Prevents SQL injection, blocks destructive commands, and calculates risk indices (1-5 scale).
   - **Analytics Agent**: Suggests charts (Bar, Line, Area, Pie), creates KPI cards, and summarizes output trends.
3. **Safe Execution Sandbox**: Four distinct execution security profiles:
   - `SAFE`: Strictly limits runs to read-only (`SELECT`) statements.
   - `APPROVAL`: Intercepts modifications (`INSERT`, `UPDATE`, `DELETE`) and prompts for manual admin confirmations.
   - `SANDBOX` *(SQLite Exclusive)*: Clones database state to an isolated temporary file, runs write modifications, captures metrics (rows affected, state changes), and destroys the replica—preserving the original database intact.
   - `AUTONOMOUS`: Directly commits modifications.
4. **Agentic Automation Workflows**: Built-in scheduler using `apscheduler` to run custom cron routines (e.g. daily, hourly query runs) and execute follow-up actions like dispatching mock emails or HTTP webhooks.
5. **Database Vault**: Local AES-256 encrypted registry storing connection configs and file paths securely.
6. **Analytics Visualizer**: Beautiful dashboard widgets and chart renders powered by Recharts, with JSON and CSV export capabilities.
7. **Compliance Audits**: A detailed ledger trace recording user actions, executed queries, rows affected, and connection changes.

---

## 📁 Project Structure

```text
├── backend/
│   ├── config.py             # Settings, encryption keys, and environment variables
│   ├── database.py           # Vault manager, schema scanning, & mock database generator
│   ├── vector_store.py       # Local SQLite FTS5 indexer for schema RAG queries
│   ├── security_sandbox.py   # Row estimator, plan explains, and SQLite sandbox replicas
│   ├── agents.py             # Multi-Agent systems and Gemini orchestrator
│   ├── workflows.py          # Background schedulers, webhook alerts, and email notifications
│   ├── requirements.txt      # Python dependencies (FastAPI, Cryptodome, etc.)
│   └── main.py               # API endpoints, middleware, and audit logs
│
├── frontend/
│   ├── package.json          # Node dependencies (Next.js, Tailwind v4, Recharts, Lucide)
│   └── src/
│       └── app/
│           ├── globals.css   # Dark theme variable tokens & custom scrollbars
│           ├── layout.tsx    # Head details, responsive viewports, and SEO tags
│           └── page.tsx      # Unified React workspace panel (Chat, Vault, Sandbox, Audit)
│
├── test_backend.py           # Unit tests for backend database, sandbox, & agents
├── run.ps1                   # Powershell script launching both servers in parallel
└── README.md                 # Project handbook
```

---

## 🛠️ Setup & Running Locally

### Prerequisites
- **Python 3.12+**
- **Node.js 20+**
- **Windows PowerShell**

### Quick Launch
QueryFlow AI includes a unified powershell script to install dependencies, compile assets, and launch services.

1. Clone or download this project workspace.
2. Open your terminal in the project root folder.
3. Run the launcher script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\run.ps1
   ```
This script will start:
- **FastAPI backend** on [http://localhost:8000](http://localhost:8000)
- **Next.js frontend** on [http://localhost:3000](http://localhost:3000)

---

## ⚙️ Configuration & Environment Variables

Create a `.env` file in the root workspace (or set these inside your terminal) to customize runtime parameters:

```env
# Google Gemini API Key to enable live LLM generation
# If left blank, QueryFlow falls back to an integrated ecommerce mockup engine
GEMINI_API_KEY=AIzaSy...

# Secret key used for AES-256 encryption in database connection vault
QUERYFLOW_ENCRYPTION_KEY=qF_default_secret_key_32_bytes_len!
```

---

## 🧪 Running Verification Tests

To verify that the encryption, schema search index, mock fallbacks, database sandboxes, and agent orchestrators are running correctly, activate your environment and execute the unit tests:

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Run backend tests
python -m unittest test_backend.py
```

---

## 🔒 Security & Safe Operations

Before executing any statement generated by the AI, the security layer conducts checks:
- **Destructive operations** (like `DROP TABLE` or global deletions without `WHERE` conditions) are caught and rejected.
- **Transactions** are automatically rolled back if execution errors occur.
- **SANDBOX mode** isolates database mutations, ensuring live production schemas are safe from destructive actions during trial queries.
