"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Database,
  Terminal,
  Play,
  ShieldAlert,
  Sparkles,
  Activity,
  Clock,
  Trash2,
  Plus,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Download,
  ArrowRight,
  Mail,
  Bell,
  Globe,
  HelpCircle,
  Code,
  Send,
  Eye,
  Settings,
  ShieldCheck,
  TrendingUp,
  FileSpreadsheet
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from "recharts";

// Interfaces
interface Connection {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
}

interface Message {
  sender: "user" | "ai";
  text: string;
  query?: string;
  explanation?: string;
  alternative_query?: string;
  validation?: {
    valid: boolean;
    errors: string[];
    warnings: string[];
  };
  security?: {
    risk_score: number;
    reasoning: string;
    safe_to_execute: boolean;
  };
  relevant_tables?: string[];
}

interface Workflow {
  id: string;
  name: string;
  connection_id: string;
  query: string;
  trigger_type: string;
  cron_expr: string;
  actions: Array<{ type: string; to?: string; url?: string }>;
  active: boolean;
  last_run: string | null;
}

interface AuditLog {
  timestamp: string;
  event_type: string;
  detail: string;
  user: string;
  status: string;
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<"copilot" | "connections" | "sandbox" | "workflows" | "audit">("copilot");
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnId, setSelectedConnId] = useState<string>("sample_sqlite");
  
  // Copilot Chat States
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ai",
      text: "Welcome to QueryFlow AI. I am your autonomous database copilot. Ask me questions in natural language, and I will generate secure queries and visualize insights.",
    }
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Connection Builder States
  const [newConnName, setNewConnName] = useState("");
  const [newConnType, setNewConnType] = useState("sqlite");
  const [newConnPath, setNewConnPath] = useState("");
  const [newConnUri, setNewConnUri] = useState("mongodb://localhost:27017");
  const [testingConnection, setTestingConnection] = useState(false);
  const [connTestMessage, setConnTestMessage] = useState<{ success?: boolean; text: string } | null>(null);

  // Sandbox SQL States
  const [sandboxQuery, setSandboxQuery] = useState("SELECT * FROM sales LIMIT 10;");
  const [sandboxMode, setSandboxMode] = useState<"SAFE" | "APPROVAL" | "SANDBOX" | "AUTONOMOUS">("APPROVAL");
  const [sandboxLoading, setSandboxLoading] = useState(false);
  const [sandboxError, setSandboxError] = useState<string | null>(null);
  const [sandboxResult, setSandboxResult] = useState<any>(null);
  const [pendingApprovalQuery, setPendingApprovalQuery] = useState<any>(null);

  // Workflows States
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [newFlowName, setNewFlowName] = useState("");
  const [newFlowQuery, setNewFlowQuery] = useState("");
  const [newFlowCron, setNewFlowCron] = useState("*/5 * * * *");
  const [actionType, setActionType] = useState<"email" | "webhook">("email");
  const [actionDest, setActionDest] = useState("admin@queryflow.ai");
  const [workflowLoading, setWorkflowLoading] = useState(false);

  // Admin Logs
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // Fetch connections and initial state
  useEffect(() => {
    fetchConnections();
    fetchWorkflows();
    fetchAuditLogs();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchConnections = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/connections");
      if (res.ok) {
        const data = await res.json();
        setConnections(data);
        if (data.length > 0 && !selectedConnId) {
          setSelectedConnId(data[0].id);
        }
      }
    } catch (e) {
      console.error("Failed to load connections:", e);
    }
  };

  const fetchWorkflows = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/workflows");
      if (res.ok) {
        setWorkflows(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAuditLogs = async () => {
    setAuditLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/audit-logs");
      if (res.ok) {
        setAuditLogs(await res.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setAuditLoading(false);
    }
  };

  // NLP Generation Submission
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userMsgText = chatInput;
    setChatInput("");
    setMessages(prev => [...prev, { sender: "user", text: userMsgText }]);
    setChatLoading(true);

    try {
      // Build brief chat history formatting for AI Agent
      const formattedHistory = messages
        .filter(m => m.text)
        .slice(-6)
        .map(m => ({
          role: m.sender === "user" ? "user" : "model",
          text: m.text
        }));

      const res = await fetch("http://localhost:8000/api/v1/query/copilot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json_encoded({
          user_query: userMsgText,
          connection_id: selectedConnId,
          chat_history: formattedHistory
        })
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = await res.json();
      if (data.success) {
        setMessages(prev => [
          ...prev,
          {
            sender: "ai",
            text: `Generated query code for "${userMsgText}".`,
            query: data.query,
            explanation: data.explanation,
            alternative_query: data.alternative_query,
            validation: data.validation,
            security: data.security,
            relevant_tables: data.relevant_tables
          }
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          { sender: "ai", text: `I encountered an issue generating the query: ${data.error || "Unknown error."}` }
        ]);
      }
    } catch (error: any) {
      setMessages(prev => [
        ...prev,
        { sender: "ai", text: `Error connecting to NLP service: ${error.message || error}` }
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const json_encoded = (obj: any) => JSON.stringify(obj);

  // Send Generated SQL directly to execution playground
  const sendToSandbox = (query: string) => {
    setSandboxQuery(query);
    setSandboxResult(null);
    setSandboxError(null);
    setActiveTab("sandbox");
  };

  // Connection Builder Actions
  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnTestMessage(null);
    const config = newConnType === "sqlite" ? { database_path: newConnPath } : { uri: newConnUri };
    
    try {
      const res = await fetch("http://localhost:8000/api/v1/connections/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json_encoded({ name: newConnName || "Test", type: newConnType, config })
      });
      const data = await res.json();
      setConnTestMessage({ success: data.success, text: data.message });
    } catch (e) {
      setConnTestMessage({ success: false, text: "Backend service unreachable." });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleCreateConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newConnName.trim()) return;
    const config = newConnType === "sqlite" ? { database_path: newConnPath } : { uri: newConnUri };
    
    try {
      const res = await fetch("http://localhost:8000/api/v1/connections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json_encoded({ name: newConnName, type: newConnType, config })
      });
      
      if (res.ok) {
        setNewConnName("");
        setNewConnPath("");
        fetchConnections();
        fetchAuditLogs();
        setConnTestMessage({ success: true, text: "Database connection registered and scanned successfully!" });
      } else {
        const err = await res.json();
        setConnTestMessage({ success: false, text: err.detail || "Validation failed." });
      }
    } catch (e) {
      setConnTestMessage({ success: false, text: "Server submission failure." });
    }
  };

  const handleDeleteConnection = async (id: string) => {
    if (id === "sample_sqlite") {
      alert("Sample database connection is protected and cannot be deleted.");
      return;
    }
    if (!confirm("Are you sure you want to delete this connection profile?")) return;
    try {
      const res = await fetch(`http://localhost:8000/api/v1/connections/${id}`, { method: "DELETE" });
      if (res.ok) {
        fetchConnections();
        fetchAuditLogs();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRescanConnection = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/connections/${id}/rescan`, { method: "POST" });
      if (res.ok) {
        alert("Database structure scanned and indexed into Vector RAG successfully.");
        fetchAuditLogs();
      }
    } catch (e) {
      alert("Rescan failed.");
    }
  };

  // Safe Query Executor Actions
  const handleExecuteQuery = async (approved: boolean = false) => {
    setSandboxLoading(true);
    setSandboxError(null);
    setSandboxResult(null);
    setPendingApprovalQuery(null);

    try {
      const res = await fetch("http://localhost:8000/api/v1/query/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json_encoded({
          connection_id: selectedConnId,
          query: sandboxQuery,
          mode: sandboxMode,
          approved
        })
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = await res.json();
      if (data.approval_required) {
        setPendingApprovalQuery(data);
      } else if (data.success) {
        setSandboxResult(data);
        fetchAuditLogs();
      } else {
        setSandboxError(data.error || "Query execution failed.");
      }
    } catch (e: any) {
      setSandboxError(e.message || "Database engine execution error.");
    } finally {
      setSandboxLoading(false);
    }
  };

  // Automation Workflows Actions
  const handleCreateWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFlowName.trim() || !newFlowQuery.trim()) return;

    setWorkflowLoading(true);
    const actions = actionType === "email" 
      ? [{ type: "email", to: actionDest }]
      : [{ type: "webhook", url: actionDest }];

    try {
      const res = await fetch("http://localhost:8000/api/v1/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: json_encoded({
          name: newFlowName,
          connection_id: selectedConnId,
          query: newFlowQuery,
          trigger_type: "cron",
          cron_expr: newFlowCron,
          actions
        })
      });

      if (res.ok) {
        setNewFlowName("");
        setNewFlowQuery("");
        fetchWorkflows();
        fetchAuditLogs();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setWorkflowLoading(false);
    }
  };

  const handleDeleteWorkflow = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/workflows/${id}`, { method: "DELETE" });
      if (res.ok) {
        fetchWorkflows();
        fetchAuditLogs();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleWorkflow = async (id: string, active: boolean) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/workflows/${id}/toggle?active=${active}`, { method: "POST" });
      if (res.ok) {
        fetchWorkflows();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerWorkflow = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/workflows/${id}/run`, { method: "POST" });
      if (res.ok) {
        alert("Workflow executed successfully in background.");
        fetchAuditLogs();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Export Results Actions
  const exportData = (format: "json" | "csv") => {
    if (!sandboxResult || !sandboxResult.rows) return;
    
    let content = "";
    let mimeType = "";
    let filename = `query_export_${Date.now()}`;
    
    if (format === "json") {
      content = JSON.stringify(sandboxResult.rows, null, 2);
      mimeType = "application/json";
      filename += ".json";
    } else {
      const cols = sandboxResult.columns;
      const rows = sandboxResult.rows;
      content = cols.join(",") + "\n";
      rows.forEach((row: any) => {
        content += cols.map((c: string) => `"${String(row[c] || '').replace(/"/g, '""')}"`).join(",") + "\n";
      });
      mimeType = "text/csv";
      filename += ".csv";
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Recharts color list
  const COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#3b82f6", "#10b981", "#f59e0b"];

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 font-sans overflow-hidden">
      
      {/* Sidebar navigation */}
      <aside className="w-64 border-r border-zinc-800 bg-zinc-900/60 backdrop-blur-md flex flex-col justify-between shrink-0">
        <div>
          {/* Brand Header */}
          <div className="p-6 border-b border-zinc-800 flex items-center gap-3">
            <div className="p-2 bg-gradient-to-tr from-indigo-600 to-purple-500 rounded-lg shadow-md shadow-indigo-500/20">
              <Sparkles className="h-5 w-5 text-white animate-pulse" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-none bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">QueryFlow AI</h1>
              <span className="text-[10px] text-zinc-500 font-medium uppercase tracking-wider">Database Platform</span>
            </div>
          </div>

          {/* Active Connection selector */}
          <div className="p-4 border-b border-zinc-800">
            <label className="block text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">Connected Target</label>
            <div className="relative">
              <select
                value={selectedConnId}
                onChange={(e) => setSelectedConnId(e.target.value)}
                className="w-full bg-zinc-950 text-zinc-200 border border-zinc-800 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 appearance-none cursor-pointer"
              >
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.type.toUpperCase()})
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute right-3 top-2.5 text-zinc-400 text-[10px]">▼</div>
            </div>
          </div>

          {/* Main Tabs */}
          <nav className="p-4 space-y-1.5">
            <button
              onClick={() => setActiveTab("copilot")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "copilot"
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
            >
              <Sparkles className="h-4.5 w-4.5" />
              <span>AI Copilot Chat</span>
            </button>

            <button
              onClick={() => setActiveTab("connections")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "connections"
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
            >
              <Database className="h-4.5 w-4.5" />
              <span>Database Vault</span>
            </button>

            <button
              onClick={() => setActiveTab("sandbox")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "sandbox"
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
            >
              <Terminal className="h-4.5 w-4.5" />
              <span>SQL Sandbox Playground</span>
            </button>

            <button
              onClick={() => setActiveTab("workflows")}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "workflows"
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
            >
              <Activity className="h-4.5 w-4.5" />
              <span>Automation Workflows</span>
            </button>

            <button
              onClick={() => {
                setActiveTab("audit");
                fetchAuditLogs();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === "audit"
                  ? "bg-indigo-600/10 text-indigo-400 border-l-2 border-indigo-500"
                  : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
              }`}
            >
              <Clock className="h-4.5 w-4.5" />
              <span>Audit logs & settings</span>
            </button>
          </nav>
        </div>

        {/* System Health */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-950/40 space-y-2">
          <div className="flex items-center justify-between text-[11px] text-zinc-500 font-medium">
            <span>LLM Status</span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
              Gemini OK
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px] text-zinc-500 font-medium">
            <span>Isolation Sandbox</span>
            <span className="text-zinc-300">Enabled</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-zinc-950 overflow-hidden">
        
        {/* Tab content selection */}
        {activeTab === "copilot" && (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Header */}
            <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-indigo-400" />
                  Autonomous Copilot
                </h2>
                <p className="text-xs text-zinc-400">Translate conversational goals directly into queries and execute safely.</p>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => setMessages([{ sender: "ai", text: "Chat history cleared. How can I help you?" }])} 
                  className="px-3 py-1.5 border border-zinc-800 hover:bg-zinc-800 rounded-lg text-xs font-semibold text-zinc-400 transition"
                >
                  Clear History
                </button>
              </div>
            </div>

            {/* Chat Screen */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.map((m, idx) => (
                <div key={idx} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-2xl rounded-2xl p-4 space-y-3 shadow-md ${
                    m.sender === "user" 
                      ? "bg-indigo-600 text-white rounded-br-none" 
                      : "bg-zinc-900 border border-zinc-800 text-zinc-100 rounded-bl-none"
                  }`}>
                    {/* Raw content text */}
                    <div className="text-xs leading-relaxed whitespace-pre-wrap">{m.text}</div>
                    
                    {/* Generated SQL Detail Card */}
                    {m.query && (
                      <div className="mt-3 bg-zinc-950 border border-zinc-800/80 rounded-xl p-3 space-y-2 text-zinc-300 font-mono">
                        <div className="flex items-center justify-between text-[10px] text-zinc-400 pb-2 border-b border-zinc-800">
                          <span className="flex items-center gap-1.5 font-sans font-semibold text-indigo-400">
                            <Code className="h-3.5 w-3.5" />
                            GENERATED STATEMENT ({selectedConnId === "sample_sqlite" ? "SQLite Dialect" : "SQL"})
                          </span>
                          <button 
                            onClick={() => navigator.clipboard.writeText(m.query || "")}
                            className="hover:text-zinc-200 text-zinc-500 font-sans font-semibold"
                          >
                            Copy Code
                          </button>
                        </div>
                        <pre className="text-xs overflow-x-auto py-1 whitespace-pre-wrap max-h-48">{m.query}</pre>
                        
                        {/* Explanation block */}
                        {m.explanation && (
                          <div className="mt-2 text-[11px] text-zinc-400 font-sans leading-relaxed border-t border-zinc-800/60 pt-2">
                            <span className="font-semibold text-zinc-300">Explanation:</span> {m.explanation}
                          </div>
                        )}

                        {/* Analysis Risk Score Indicator */}
                        {m.security && (
                          <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] font-sans border-t border-zinc-800/60 pt-2.5">
                            <div className="flex items-center gap-2">
                              <span className="text-zinc-400 font-medium">Risk Score:</span>
                              <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                                m.security.risk_score >= 4 
                                  ? "bg-red-500/10 text-red-400 border border-red-500/30" 
                                  : m.security.risk_score >= 3 
                                  ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/30" 
                                  : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                              }`}>
                                {m.security.risk_score}/5 ({m.security.risk_score >= 4 ? "High Risk" : m.security.risk_score >= 3 ? "Medium" : "Safe"})
                              </span>
                            </div>
                            
                            {m.validation && (
                              <div className="flex items-center gap-1.5 text-zinc-400 font-medium">
                                <span>Syntax:</span>
                                {m.validation.valid ? (
                                  <span className="text-emerald-400 flex items-center gap-1">
                                    <CheckCircle className="h-3 w-3" /> Validated
                                  </span>
                                ) : (
                                  <span className="text-red-400 flex items-center gap-1">
                                    <AlertTriangle className="h-3 w-3" /> Syntax Error
                                  </span>
                                )}
                              </div>
                            )}
                            
                            <button
                              onClick={() => sendToSandbox(m.query || "")}
                              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition"
                            >
                              Sandbox Query
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-zinc-900 border border-zinc-800 rounded-2xl rounded-bl-none p-4 shadow-md space-y-2 max-w-sm">
                    <div className="flex items-center gap-2 text-xs text-zinc-400 font-medium">
                      <RefreshCw className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                      <span>Schema, Security & Query Agents processing...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input Console */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-900/40">
              <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="e.g. 'Show total sales from last month grouped by region' or 'Find inactive customers'..."
                  className="flex-1 bg-zinc-950 border border-zinc-800 hover:border-zinc-700 focus:border-indigo-500 rounded-xl px-4 py-3 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-all"
                  disabled={chatLoading}
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  className="px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/40 text-white rounded-xl flex items-center justify-center transition-all cursor-pointer"
                >
                  <Send className="h-4.5 w-4.5" />
                </button>
              </form>
              <div className="flex justify-center gap-4 mt-2.5 text-[11px] text-zinc-500 font-medium">
                <button type="button" onClick={() => setChatInput("Show total sales from last month grouped by region")} className="hover:text-indigo-400 transition">Show sales by region</button>
                <span>•</span>
                <button type="button" onClick={() => setChatInput("Find inactive customers")} className="hover:text-indigo-400 transition">Find inactive customers</button>
                <span>•</span>
                <button type="button" onClick={() => setChatInput("Show products lowest in stock")} className="hover:text-indigo-400 transition">Lowest stock levels</button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "connections" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div>
              <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                <Database className="h-5 w-5 text-indigo-400" />
                Database Vault & Credential Registry
              </h2>
              <p className="text-xs text-zinc-400">Configure connection strings securely. All credentials are encrypted using local AES-256 vault configurations.</p>
            </div>

            {/* Grid layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Registered Profiles */}
              <div className="lg:col-span-2 space-y-4">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Registered Connections</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {connections.map((c) => (
                    <div key={c.id} className="p-4 bg-zinc-900 border border-zinc-800 rounded-xl space-y-3 relative group">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-bold text-xs text-zinc-100">{c.name}</h4>
                          <span className="text-[10px] bg-zinc-950 text-indigo-400 font-semibold px-2 py-0.5 rounded-full uppercase border border-zinc-800/80">
                            {c.type}
                          </span>
                        </div>
                        <div className="flex gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleRescanConnection(c.id)}
                            title="Rescan database schema & index RAG vectors"
                            className="p-1 hover:text-indigo-400 text-zinc-400 transition"
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteConnection(c.id)}
                            title="Remove profile"
                            className="p-1 hover:text-red-400 text-zinc-400 transition"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>

                      <div className="text-[11px] text-zinc-400 space-y-1 bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800/60 font-mono overflow-hidden text-ellipsis">
                        {c.type === "sqlite" ? (
                          <div>Path: {c.config.database_path || "samples.db"}</div>
                        ) : (
                          <div>URI: {c.config.uri || "mongodb://..."}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Registry Creator Form */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4 h-fit">
                <h3 className="text-xs font-semibold text-zinc-100">Add Connection Profile</h3>
                
                <form onSubmit={handleCreateConnection} className="space-y-4">
                  <div>
                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Profile Name</label>
                    <input
                      type="text"
                      value={newConnName}
                      onChange={(e) => setNewConnName(e.target.value)}
                      placeholder="e.g. Analytics Postgres"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Database Type</label>
                    <select
                      value={newConnType}
                      onChange={(e) => setNewConnType(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer"
                    >
                      <option value="sqlite">SQLite</option>
                      <option value="postgresql">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="mongodb">MongoDB</option>
                      <option value="snowflake">Snowflake</option>
                    </select>
                  </div>

                  {newConnType === "sqlite" ? (
                    <div>
                      <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Local SQLite DB Path</label>
                      <input
                        type="text"
                        value={newConnPath}
                        onChange={(e) => setNewConnPath(e.target.value)}
                        placeholder="e.g. D:\project\db.sqlite"
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                      />
                    </div>
                  ) : (
                    <div>
                      <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Connection URI</label>
                      <input
                        type="text"
                        value={newConnUri}
                        onChange={(e) => setNewConnUri(e.target.value)}
                        placeholder="postgresql://user:pass@host:port/dbname"
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                      />
                    </div>
                  )}

                  {connTestMessage && (
                    <div className={`p-3 rounded-lg text-xs leading-relaxed ${
                      connTestMessage.success 
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                        : "bg-red-500/10 text-red-400 border border-red-500/20"
                    }`}>
                      {connTestMessage.text}
                    </div>
                  )}

                  <div className="flex gap-2 pt-2">
                    <button
                      type="button"
                      disabled={testingConnection}
                      onClick={handleTestConnection}
                      className="flex-1 py-2 border border-zinc-800 hover:bg-zinc-800 text-zinc-400 rounded-lg text-xs font-semibold transition"
                    >
                      {testingConnection ? "Testing..." : "Test Connection"}
                    </button>
                    <button
                      type="submit"
                      className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition"
                    >
                      Save Profile
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {activeTab === "sandbox" && (
          <div className="flex-1 flex flex-col min-h-0 p-6 space-y-6 overflow-y-auto">
            {/* Header */}
            <div>
              <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                <Terminal className="h-5 w-5 text-indigo-400" />
                Query Execution Playground
              </h2>
              <p className="text-xs text-zinc-400">Run database commands manually. Select security execution profiles depending on query risk assessment.</p>
            </div>

            {/* Sandbox main panel */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
              
              {/* Editor Console */}
              <div className="xl:col-span-2 space-y-4">
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
                  {/* Select parameters */}
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider">Dialect Target:</span>
                      <span className="text-xs bg-zinc-950 border border-zinc-800 text-zinc-300 font-mono px-2 py-0.5 rounded-full font-bold">
                        {connections.find(c => c.id === selectedConnId)?.type.toUpperCase() || "SQL"}
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-400 font-semibold uppercase tracking-wider">Execution Mode:</span>
                      <div className="flex bg-zinc-950 p-1 rounded-lg border border-zinc-800/80">
                        {(["SAFE", "APPROVAL", "SANDBOX", "AUTONOMOUS"] as const).map((m) => (
                          <button
                            key={m}
                            type="button"
                            onClick={() => setSandboxMode(m)}
                            className={`px-2 py-1 rounded text-[10px] font-bold transition-all ${
                              sandboxMode === m 
                                ? "bg-indigo-600 text-white" 
                                : "text-zinc-500 hover:text-zinc-300"
                            }`}
                          >
                            {m}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Code Editor */}
                  <div className="border border-zinc-800 rounded-xl bg-zinc-950 p-4 font-mono text-xs">
                    <textarea
                      value={sandboxQuery}
                      onChange={(e) => setSandboxQuery(e.target.value)}
                      rows={6}
                      className="w-full bg-transparent text-zinc-200 border-none outline-none resize-none font-mono focus:ring-0 leading-relaxed"
                      placeholder="Write SQL statements here..."
                    />
                  </div>

                  {/* Submit buttons */}
                  <div className="flex items-center justify-between">
                    <div className="text-[11px] text-zinc-500 leading-none">
                      {sandboxMode === "SANDBOX" && "⚠️ Sandboxed SQLite clones will automatically discard modifications after run."}
                      {sandboxMode === "SAFE" && "🔒 Restricted to SELECT query statements only."}
                    </div>
                    <button
                      onClick={() => handleExecuteQuery(false)}
                      disabled={sandboxLoading || !sandboxQuery.trim()}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/40 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition cursor-pointer"
                    >
                      {sandboxLoading ? (
                        <>
                          <RefreshCw className="h-4.5 w-4.5 animate-spin" /> Running...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4" /> Execute Query
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Error Card */}
                {sandboxError && (
                  <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-xs text-red-400 flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-bold mb-1">Database Execution Exception</h4>
                      <pre className="font-mono text-[11px] whitespace-pre-wrap leading-relaxed">{sandboxError}</pre>
                    </div>
                  </div>
                )}

                {/* Approval Prompt Modal Card */}
                {pendingApprovalQuery && (
                  <div className="p-5 bg-yellow-500/10 border border-yellow-500/30 rounded-xl space-y-4">
                    <div className="flex items-start gap-3">
                      <ShieldAlert className="h-6 w-6 text-yellow-400 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="font-bold text-sm text-yellow-400 leading-tight">Write Modification Approval Required</h4>
                        <p className="text-xs text-zinc-400 leading-relaxed mt-1">
                          You are attempting to execute a data modification command (`{pendingApprovalQuery.query_type}`) on connection. Click continue to commit transaction.
                        </p>
                      </div>
                    </div>

                    <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 font-mono text-xs text-zinc-300">
                      {pendingApprovalQuery.query}
                    </div>

                    <div className="flex justify-end gap-2 text-xs font-semibold">
                      <button
                        onClick={() => setPendingApprovalQuery(null)}
                        className="px-3 py-1.5 border border-zinc-800 hover:bg-zinc-800 text-zinc-400 rounded-lg transition"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleExecuteQuery(true)}
                        className="px-4 py-1.5 bg-yellow-500 hover:bg-yellow-600 text-zinc-950 rounded-lg transition"
                      >
                        Approve & Commit Changes
                      </button>
                    </div>
                  </div>
                )}

                {/* Results Visual Output */}
                {sandboxResult && (
                  <div className="space-y-4">
                    {/* Performance Cost & Sandbox indicator Banner */}
                    <div className="flex flex-wrap gap-4 items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2 text-xs">
                      <div className="flex items-center gap-4 text-zinc-400">
                        <span>Affected: <strong className="text-zinc-200">{sandboxResult.rows_affected}</strong> rows</span>
                        <span>Time: <strong className="text-zinc-200">{sandboxResult.duration_ms}ms</strong></span>
                        <span>Performance: <strong className={`text-${sandboxResult.performance?.cost_score === "Low" ? "emerald-400" : "yellow-400"}`}>{sandboxResult.performance?.cost_score || "Low"}</strong></span>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {sandboxResult.sandbox_simulated && (
                          <span className="bg-indigo-600/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20 text-[10px] font-bold">
                            SANDBOX SIMULATED
                          </span>
                        )}
                        
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => exportData("csv")}
                            className="p-1 hover:text-indigo-400 text-zinc-400 transition"
                            title="Export to CSV"
                          >
                            <FileSpreadsheet className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => exportData("json")}
                            className="p-1 hover:text-indigo-400 text-zinc-400 transition"
                            title="Export to JSON"
                          >
                            <Download className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Dynamic charts component */}
                    {sandboxResult.analytics && sandboxResult.analytics.chart_type !== "table" && (
                      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
                        <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">{sandboxResult.analytics.chart_title}</h4>
                        <div className="h-64 w-full text-xs">
                          <ResponsiveContainer width="100%" height="100%">
                            {sandboxResult.analytics.chart_type === "bar" ? (
                              <BarChart data={sandboxResult.rows}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                <XAxis dataKey={sandboxResult.analytics.x_axis_field} stroke="#71717a" />
                                <YAxis stroke="#71717a" />
                                <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a" }} />
                                <Legend />
                                {sandboxResult.analytics.y_axis_fields.map((f: string, i: number) => (
                                  <Bar key={f} dataKey={f} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
                                ))}
                              </BarChart>
                            ) : sandboxResult.analytics.chart_type === "line" ? (
                              <LineChart data={sandboxResult.rows}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                <XAxis dataKey={sandboxResult.analytics.x_axis_field} stroke="#71717a" />
                                <YAxis stroke="#71717a" />
                                <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a" }} />
                                <Legend />
                                {sandboxResult.analytics.y_axis_fields.map((f: string, i: number) => (
                                  <Line key={f} type="monotone" dataKey={f} stroke={COLORS[i % COLORS.length]} strokeWidth={2} />
                                ))}
                              </LineChart>
                            ) : sandboxResult.analytics.chart_type === "area" ? (
                              <AreaChart data={sandboxResult.rows}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                <XAxis dataKey={sandboxResult.analytics.x_axis_field} stroke="#71717a" />
                                <YAxis stroke="#71717a" />
                                <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a" }} />
                                <Legend />
                                {sandboxResult.analytics.y_axis_fields.map((f: string, i: number) => (
                                  <Area key={f} type="monotone" dataKey={f} fill={COLORS[i % COLORS.length] + "20"} stroke={COLORS[i % COLORS.length]} strokeWidth={2} />
                                ))}
                              </AreaChart>
                            ) : (
                              <PieChart>
                                <Pie
                                  data={sandboxResult.rows}
                                  cx="50%"
                                  cy="50%"
                                  labelLine={false}
                                  label={({ name, percent }) => `${name} ${percent ? (percent * 100).toFixed(0) : 0}%`}
                                  outerRadius={80}
                                  fill="#8884d8"
                                  dataKey={sandboxResult.analytics.y_axis_fields[0]}
                                  nameKey={sandboxResult.analytics.x_axis_field}
                                >
                                  {sandboxResult.rows.map((entry: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                  ))}
                                </Pie>
                                <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a" }} />
                              </PieChart>
                            )}
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}

                    {/* Table View */}
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                      <div className="overflow-x-auto max-h-96">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="bg-zinc-950 border-b border-zinc-800 text-zinc-400 font-semibold">
                              {sandboxResult.columns.map((c: string) => (
                                <th key={c} className="p-3 uppercase tracking-wider">{c}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-800/60 font-mono">
                            {sandboxResult.rows.map((row: any, rIdx: number) => (
                              <tr key={rIdx} className="hover:bg-zinc-800/20 text-zinc-300">
                                {sandboxResult.columns.map((c: string) => (
                                  <td key={c} className="p-3 truncate max-w-xs">{String(row[c] !== undefined ? row[c] : "")}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Sidebar Analytics summary details */}
              <div className="space-y-6">
                {sandboxResult && sandboxResult.analytics && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <h3 className="text-xs font-bold text-zinc-100 flex items-center gap-1.5">
                      <TrendingUp className="h-4.5 w-4.5 text-indigo-400" />
                      AUTO ANALYTICS INSIGHTS
                    </h3>
                    
                    {sandboxResult.analytics.summary && (
                      <p className="text-xs text-zinc-400 leading-relaxed">{sandboxResult.analytics.summary}</p>
                    )}

                    {/* KPIs cards */}
                    {sandboxResult.analytics.kpis && sandboxResult.analytics.kpis.length > 0 && (
                      <div className="grid grid-cols-2 gap-3 pt-2">
                        {sandboxResult.analytics.kpis.map((kpi: any, idx: number) => (
                          <div key={idx} className="p-3 bg-zinc-950 rounded-lg border border-zinc-800/80">
                            <span className="block text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">{kpi.label}</span>
                            <span className="block text-base font-bold text-zinc-100 mt-1 font-mono">{kpi.value}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Explanation Card */}
                {sandboxResult && sandboxResult.performance && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
                    <h3 className="text-xs font-bold text-zinc-100 flex items-center gap-1.5">
                      <HelpCircle className="h-4.5 w-4.5 text-indigo-400" />
                      EXPLAIN CODE PLAN
                    </h3>
                    <div className="space-y-3 text-[11px] leading-relaxed text-zinc-400">
                      <div>
                        <span className="block font-semibold text-zinc-300">Scan plan:</span>
                        <div className="bg-zinc-950 p-2.5 rounded border border-zinc-800 mt-1 font-mono text-[10px] space-y-1">
                          {sandboxResult.performance.query_plan.map((p: string, i: number) => (
                            <div key={i}>{p}</div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <span>Cost metric evaluation finished in {sandboxResult.performance.explain_duration_ms}ms.</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

            </div>
          </div>
        )}

        {activeTab === "workflows" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div>
              <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                <Activity className="h-5 w-5 text-indigo-400" />
                Autonomous Automation Pipeline
              </h2>
              <p className="text-xs text-zinc-400">Register database cron schedules. Query results are evaluated automatically and sent to email endpoints or webhook microservices.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
              {/* Active Jobs */}
              <div className="lg:col-span-2 space-y-4">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Scheduled Workflows</h3>
                
                <div className="space-y-4">
                  {workflows.length === 0 ? (
                    <div className="p-8 text-center text-xs text-zinc-500 border border-zinc-800 border-dashed rounded-xl">
                      No automated database workflows registered. Create one below.
                    </div>
                  ) : (
                    workflows.map((w) => (
                      <div key={w.id} className="p-4 bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-3">
                            <h4 className="font-bold text-xs text-zinc-100">{w.name}</h4>
                            <span className="text-[9px] bg-indigo-950 text-indigo-400 border border-indigo-900/50 px-2 py-0.5 rounded font-bold font-mono">
                              {w.cron_expr}
                            </span>
                          </div>
                          
                          <pre className="text-[10px] text-zinc-400 font-mono py-1 max-w-xl truncate">{w.query}</pre>
                          
                          <div className="flex items-center gap-4 text-[10px] text-zinc-500">
                            {w.actions.map((act, i) => (
                              <span key={i} className="flex items-center gap-1">
                                {act.type === "email" ? <Mail className="h-3 w-3" /> : <Globe className="h-3 w-3" />}
                                {act.type === "email" ? `Mail to ${act.to}` : `Webhook post to ${act.url}`}
                              </span>
                            ))}
                            {w.last_run && (
                              <span>Last execution: {new Date(w.last_run).toLocaleTimeString()}</span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-3 self-end md:self-center shrink-0">
                          {/* Toggle active state */}
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={w.active}
                              onChange={(e) => handleToggleWorkflow(w.id, e.target.checked)}
                              className="sr-only peer"
                            />
                            <div className="w-9 h-5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-zinc-400 after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600 peer-checked:after:bg-white border border-zinc-800"></div>
                          </label>

                          <button
                            onClick={() => handleTriggerWorkflow(w.id)}
                            className="p-1 text-zinc-400 hover:text-zinc-200 transition"
                            title="Run immediately"
                          >
                            <Play className="h-4.5 w-4.5" />
                          </button>

                          <button
                            onClick={() => handleDeleteWorkflow(w.id)}
                            className="p-1 text-zinc-400 hover:text-red-400 transition"
                            title="Delete"
                          >
                            <Trash2 className="h-4.5 w-4.5" />
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Creator Form */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
                <h3 className="text-xs font-semibold text-zinc-100">Schedule Database Job</h3>
                
                <form onSubmit={handleCreateWorkflow} className="space-y-4 text-xs">
                  <div>
                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Workflow Name</label>
                    <input
                      type="text"
                      value={newFlowName}
                      onChange={(e) => setNewFlowName(e.target.value)}
                      placeholder="e.g. Sales Report Scheduler"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Cron Expression</label>
                    <input
                      type="text"
                      value={newFlowCron}
                      onChange={(e) => setNewFlowCron(e.target.value)}
                      placeholder="*/5 * * * * (Every 5 mins)"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Query Code</label>
                    <textarea
                      value={newFlowQuery}
                      onChange={(e) => setNewFlowQuery(e.target.value)}
                      rows={4}
                      placeholder="SELECT * FROM sales WHERE amount > 500;"
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono resize-none"
                    />
                  </div>

                  <div className="border-t border-zinc-800/80 pt-3">
                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-2 font-bold">Dispatch Action Type</label>
                    <div className="flex gap-3 mb-3">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name="action_type"
                          checked={actionType === "email"}
                          onChange={() => { setActionType("email"); setActionDest("admin@queryflow.ai"); }}
                          className="text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                        <span>Email alert</span>
                      </label>
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name="action_type"
                          checked={actionType === "webhook"}
                          onChange={() => { setActionType("webhook"); setActionDest("https://api.workplace.com/hooks"); }}
                          className="text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                        <span>Webhook HTTP POST</span>
                      </label>
                    </div>

                    <label className="block text-[10px] text-zinc-400 uppercase tracking-wider mb-1 font-bold">Destination URL / Address</label>
                    <input
                      type="text"
                      value={actionDest}
                      onChange={(e) => setActionDest(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={workflowLoading || !newFlowName || !newFlowQuery}
                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-600/40 text-white rounded-lg text-xs font-semibold transition cursor-pointer"
                  >
                    {workflowLoading ? "Registering..." : "Schedule Workflow"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {activeTab === "audit" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                  <Clock className="h-5 w-5 text-indigo-400" />
                  Compliance Center & Audit Logs
                </h2>
                <p className="text-xs text-zinc-400">View real-time traces of database transactions, validation errors, and automated job triggers.</p>
              </div>
              <button
                onClick={fetchAuditLogs}
                disabled={auditLoading}
                className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition text-zinc-300"
              >
                <RefreshCw className={`h-4 w-4 ${auditLoading ? 'animate-spin' : ''}`} />
                Reload Feed
              </button>
            </div>

            {/* Audit log Table */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-zinc-950 border-b border-zinc-800 text-zinc-400 font-semibold">
                      <th className="p-3">Timestamp</th>
                      <th className="p-3">Event Type</th>
                      <th className="p-3">Description</th>
                      <th className="p-3">Trigger User</th>
                      <th className="p-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 font-mono">
                    {auditLogs.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-zinc-500 font-sans">
                          No audit event records found.
                        </td>
                      </tr>
                    ) : (
                      auditLogs.map((log, idx) => (
                        <tr key={idx} className="hover:bg-zinc-800/20 text-zinc-300">
                          <td className="p-3 text-[10px] text-zinc-500 whitespace-nowrap">
                            {new Date(log.timestamp).toLocaleString()}
                          </td>
                          <td className="p-3">
                            <span className="bg-zinc-950 text-indigo-400 border border-zinc-800 font-semibold text-[10px] px-2 py-0.5 rounded-full uppercase">
                              {log.event_type}
                            </span>
                          </td>
                          <td className="p-3 max-w-sm truncate text-zinc-300 font-sans" title={log.detail}>
                            {log.detail}
                          </td>
                          <td className="p-3 text-zinc-400">{log.user}</td>
                          <td className="p-3">
                            <span className={`flex items-center gap-1.5 ${
                              log.status === "success" 
                                ? "text-emerald-400" 
                                : log.status === "warning" 
                                ? "text-yellow-400" 
                                : "text-red-400"
                            }`}>
                              <span className={`h-1.5 w-1.5 rounded-full ${
                                log.status === "success" 
                                  ? "bg-emerald-400" 
                                  : log.status === "warning" 
                                  ? "bg-yellow-400" 
                                  : "bg-red-400"
                              }`}></span>
                              <span className="font-sans uppercase text-[10px] font-bold">{log.status}</span>
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </main>

    </div>
  );
}
