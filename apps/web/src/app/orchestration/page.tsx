'use client';

import { useEffect, useState } from 'react';

// --- Interfaces ---

interface SpecializedAgent {
  id: string;
  name: string;
  description: string | null;
  agent_type: string;
  capabilities: string[] | null;
  allowed_tools: string[] | null;
  allowed_data_sources: string[] | null;
  permissions: Array<{ action: string; resource: string }> | null;
  risk_level: string;
  status: string;
  version: string;
  created_at: string | null;
  updated_at: string | null;
}

interface AgentTask {
  id: string;
  orchestration_id: string;
  agent_id: string;
  objective: string;
  expected_output_type: string | null;
  capabilities_required: string[] | null;
  execution_order: number;
  depends_on: string[] | null;
  status: string;
  summary: string | null;
  findings: Array<Record<string, unknown>> | null;
  recommendations: Array<Record<string, unknown>> | null;
  evidence: Array<Record<string, unknown>> | null;
  confidence: number | null;
  risks: Array<Record<string, unknown>> | null;
  required_actions: Array<Record<string, unknown>> | null;
  sources: string[] | null;
  token_usage: number;
  tool_calls: number;
  llm_calls: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface OrchestrationExecution {
  id: string;
  organization_id: string;
  user_id: string;
  objective: string;
  plan: Record<string, unknown> | null;
  status: string;
  final_summary: string | null;
  final_recommendation: Record<string, unknown> | null;
  final_confidence: number | null;
  conflicts: Array<Record<string, unknown>> | null;
  conflict_resolution: Record<string, unknown> | null;
  workflow_execution_id: string | null;
  total_token_usage: number;
  total_tool_calls: number;
  total_llm_calls: number;
  total_agent_tasks: number;
  error: string | null;
  tasks: AgentTask[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

interface AgentMetric {
  agent_id: string;
  agent_type: string;
  name: string;
  status: string;
  version: string;
  capabilities: string[] | null;
  risk_level: string;
  tasks_total: number;
  tasks_completed: number;
  tasks_failed: number;
  tasks_timed_out: number;
  success_rate: number;
  avg_latency_seconds: number;
  avg_confidence: number;
  total_token_usage: number;
  total_llm_calls: number;
  total_tool_calls: number;
  last_activity: string | null;
}

interface ExecutionTrace {
  execution_id: string;
  objective: string;
  status: string;
  plan: Record<string, unknown> | null;
  tasks: Array<{
    task_id: string;
    agent_id: string;
    objective: string;
    status: string;
    execution_order: number;
    summary: string | null;
    confidence: number | null;
    findings_count: number;
    recommendations_count: number;
    started_at: string | null;
    completed_at: string | null;
    error: string | null;
  }>;
  communications: Array<{
    from_agent: string;
    to_agent: string | null;
    type: string;
    content: string;
    created_at: string | null;
  }>;
  conflicts: Array<Record<string, unknown>> | null;
  conflict_resolution: Record<string, unknown> | null;
  final_summary: string | null;
  final_confidence: number | null;
  cost: {
    total_token_usage: number;
    total_tool_calls: number;
    total_llm_calls: number;
    total_agent_tasks: number;
  };
  audit_timeline: Array<{
    action: string;
    agent_name: string | null;
    created_at: string | null;
  }>;
  started_at: string | null;
  completed_at: string | null;
}

// --- Status colors ---

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-50 text-green-700',
  inactive: 'bg-slate-100 text-slate-600',
  deprecated: 'bg-red-50 text-red-600',
  planning: 'bg-blue-50 text-blue-700',
  executing: 'bg-blue-50 text-blue-700',
  waiting_for_approval: 'bg-orange-50 text-orange-700',
  merging_results: 'bg-purple-50 text-purple-700',
  resolving_conflicts: 'bg-amber-50 text-amber-700',
  completed: 'bg-green-50 text-green-700',
  failed: 'bg-red-50 text-red-700',
  cancelled: 'bg-slate-100 text-slate-600',
  pending: 'bg-yellow-50 text-yellow-700',
  running: 'bg-blue-50 text-blue-700',
  timed_out: 'bg-red-50 text-red-600',
};

const RISK_COLORS: Record<string, string> = {
  low: 'text-green-600',
  medium: 'text-amber-600',
  high: 'text-red-600',
  critical: 'text-red-700 font-bold',
};

const TASK_ICONS: Record<string, string> = {
  completed: '\u2713',
  failed: '\u2717',
  running: '\u25B6',
  pending: '\u25CB',
  cancelled: '\u2014',
  timed_out: '\u23F0',
};

const AGENT_TYPE_ICONS: Record<string, string> = {
  research: '\uD83D\uDD0D',
  finance: '\uD83D\uDCB0',
  sales: '\uD83D\uDCC8',
  operations: '\u2699\uFE0F',
  compliance: '\uD83D\uDCCB',
};

type Tab = 'dashboard' | 'agents' | 'executions' | 'trace' | 'metrics';

export default function OrchestrationPage() {
  const [tab, setTab] = useState<Tab>('dashboard');
  const [agents, setAgents] = useState<SpecializedAgent[]>([]);
  const [executions, setExecutions] = useState<OrchestrationExecution[]>([]);
  const [agentMetrics, setAgentMetrics] = useState<AgentMetric[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<OrchestrationExecution | null>(null);
  const [executionTrace, setExecutionTrace] = useState<ExecutionTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Execute modal
  const [showExecute, setShowExecute] = useState(false);
  const [executeObjective, setExecuteObjective] = useState('');
  const [executePlan, setExecutePlan] = useState<Record<string, unknown> | null>(null);
  const [planning, setPlanning] = useState(false);
  const [executing, setExecuting] = useState(false);

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

  // --- Data fetching ---

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/orchestration/agents', { headers: headers() });
      if (res.ok) { const d = await res.json(); setAgents(d.agents || []); }
    } catch {}
  };

  const fetchExecutions = async () => {
    try {
      const res = await fetch('/api/orchestration/executions', { headers: headers() });
      if (res.ok) { const d = await res.json(); setExecutions(d.executions || []); }
    } catch {}
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/orchestration/metrics', { headers: headers() });
      if (res.ok) { const d = await res.json(); setAgentMetrics(d.agents || []); }
    } catch {}
  };

  const fetchTrace = async (executionId: string) => {
    try {
      const res = await fetch(`/api/orchestration/executions/${executionId}/trace`, { headers: headers() });
      if (res.ok) { setExecutionTrace(await res.json()); }
    } catch {}
  };

  const fetchAll = async () => {
    setLoading(true);
    await Promise.all([fetchAgents(), fetchExecutions(), fetchMetrics()]);
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  // --- Actions ---

  const handleSeedAgents = async () => {
    try {
      const res = await fetch('/api/orchestration/agents/seed', {
        method: 'POST',
        headers: headers(),
      });
      if (res.ok) { fetchAgents(); }
    } catch {}
  };

  const handleCreatePlan = async () => {
    if (!executeObjective.trim()) return;
    setPlanning(true);
    setError(null);
    try {
      const res = await fetch('/api/orchestration/orchestrator/plan', {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ objective: executeObjective }),
      });
      if (res.ok) {
        const plan = await res.json();
        setExecutePlan(plan);
      } else {
        setError('Failed to create plan');
      }
    } catch { setError('Failed to create plan'); }
    setPlanning(false);
  };

  const handleExecute = async () => {
    if (!executeObjective.trim()) return;
    setExecuting(true);
    setError(null);
    try {
      const res = await fetch('/api/orchestration/orchestrator/execute', {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          objective: executeObjective,
          plan: executePlan || undefined,
        }),
      });
      if (res.ok) {
        setShowExecute(false);
        setExecuteObjective('');
        setExecutePlan(null);
        fetchExecutions();
      } else {
        setError('Execution failed');
      }
    } catch { setError('Execution failed'); }
    setExecuting(false);
  };

  const handleViewTrace = async (execution: OrchestrationExecution) => {
    setSelectedExecution(execution);
    await fetchTrace(execution.id);
    setTab('trace');
  };

  // --- Rendering ---

  const renderStatusBadge = (status: string) => (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );

  const renderRiskBadge = (risk: string) => (
    <span className={`text-xs font-medium ${RISK_COLORS[risk] || 'text-gray-500'}`}>
      {risk}
    </span>
  );

  const renderConfidence = (confidence: number | null) => {
    if (confidence === null || confidence === undefined) return <span className="text-gray-400">—</span>;
    const pct = Math.round(confidence * 100);
    const color = pct >= 80 ? 'text-green-600' : pct >= 50 ? 'text-amber-600' : 'text-red-600';
    return <span className={`text-sm font-medium ${color}`}>{pct}%</span>;
  };

  // --- Dashboard ---
  const renderDashboard = () => {
    const totalTasks = agentMetrics.reduce((sum, a) => sum + a.tasks_total, 0);
    const completedTasks = agentMetrics.reduce((sum, a) => sum + a.tasks_completed, 0);
    const failedTasks = agentMetrics.reduce((sum, a) => sum + a.tasks_failed, 0);
    const activeAgents = agents.filter(a => a.status === 'active').length;
    const completedExecs = executions.filter(e => e.status === 'completed').length;
    const failedExecs = executions.filter(e => e.status === 'failed').length;

    return (
      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <div className="text-2xl font-bold text-blue-600">{activeAgents}</div>
            <div className="text-sm text-gray-500">Active Agents</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <div className="text-2xl font-bold text-indigo-600">{executions.length}</div>
            <div className="text-sm text-gray-500">Orchestrations</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <div className="text-2xl font-bold text-green-600">{completedExecs}</div>
            <div className="text-sm text-gray-500">Completed</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <div className="text-2xl font-bold text-red-600">{failedExecs}</div>
            <div className="text-sm text-gray-500">Failed</div>
          </div>
        </div>

        {/* Agent Overview */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Specialized Agents</h2>
            {agents.length === 0 && (
              <button onClick={handleSeedAgents} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
                Seed Default Agents
              </button>
            )}
          </div>
          {agents.length === 0 ? (
            <p className="text-gray-500 text-sm">No agents registered. Click &quot;Seed Default Agents&quot; to initialize.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map(agent => (
                <div key={agent.id} className="border rounded-lg p-4 hover:shadow-sm transition-shadow">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xl">{AGENT_TYPE_ICONS[agent.agent_type] || '\uD83E\uDD16'}</span>
                    <span className="font-medium">{agent.name}</span>
                    {renderStatusBadge(agent.status)}
                  </div>
                  <p className="text-sm text-gray-500 mb-2">{agent.description}</p>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {(agent.capabilities || []).map(cap => (
                      <span key={cap} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs rounded">{cap}</span>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span>Risk: {renderRiskBadge(agent.risk_level)}</span>
                    <span>v{agent.version}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Orchestrations */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Orchestrations</h2>
          {executions.length === 0 ? (
            <p className="text-gray-500 text-sm">No orchestrations yet.</p>
          ) : (
            <div className="space-y-3">
              {executions.slice(0, 5).map(ex => (
                <div key={ex.id} className="border rounded-lg p-4 hover:shadow-sm cursor-pointer transition-shadow" onClick={() => handleViewTrace(ex)}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm">{ex.objective.substring(0, 100)}{ex.objective.length > 100 ? '...' : ''}</span>
                    {renderStatusBadge(ex.status)}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>{ex.total_agent_tasks} agents</span>
                    {ex.final_confidence !== null && <span>Confidence: {renderConfidence(ex.final_confidence)}</span>}
                    <span>{ex.created_at ? new Date(ex.created_at).toLocaleDateString() : ''}</span>
                  </div>
                  {/* Task progress indicators */}
                  {ex.tasks && ex.tasks.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {ex.tasks.map(task => (
                        <span key={task.id} title={`${task.objective} — ${task.status}`} className={`w-6 h-6 rounded flex items-center justify-center text-xs ${STATUS_COLORS[task.status] || 'bg-gray-100'}`}>
                          {TASK_ICONS[task.status] || '?'}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  // --- Agents tab ---
  const renderAgents = () => (
    <div className="bg-white rounded-xl shadow-sm border p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Specialized Agents</h2>
        <button onClick={handleSeedAgents} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          Seed Defaults
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2 pr-4">Agent</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Capabilities</th>
              <th className="pb-2 pr-4">Risk</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">Version</th>
              <th className="pb-2">Permissions</th>
            </tr>
          </thead>
          <tbody>
            {agents.map(agent => (
              <tr key={agent.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <span>{AGENT_TYPE_ICONS[agent.agent_type] || '\uD83E\uDD16'}</span>
                    <div>
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-xs text-gray-400">{agent.description?.substring(0, 60)}...</div>
                    </div>
                  </div>
                </td>
                <td className="py-3 pr-4"><span className="px-2 py-0.5 bg-gray-100 rounded text-xs">{agent.agent_type}</span></td>
                <td className="py-3 pr-4">
                  <div className="flex flex-wrap gap-1 max-w-xs">
                    {(agent.capabilities || []).map(cap => (
                      <span key={cap} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs rounded">{cap}</span>
                    ))}
                  </div>
                </td>
                <td className="py-3 pr-4">{renderRiskBadge(agent.risk_level)}</td>
                <td className="py-3 pr-4">{renderStatusBadge(agent.status)}</td>
                <td className="py-3 pr-4 text-gray-500">{agent.version}</td>
                <td className="py-3">
                  <div className="flex flex-wrap gap-1 max-w-xs">
                    {(agent.permissions || []).map((p, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-gray-50 text-gray-600 text-xs rounded">{p.action}:{p.resource}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  // --- Executions tab ---
  const renderExecutions = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Orchestration Executions</h2>
        <button onClick={() => setShowExecute(true)} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          New Orchestration
        </button>
      </div>
      {executions.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border p-8 text-center text-gray-500">
          No orchestrations yet. Start one by clicking &quot;New Orchestration&quot;.
        </div>
      ) : (
        <div className="space-y-3">
          {executions.map(ex => (
            <div key={ex.id} className="bg-white rounded-xl shadow-sm border p-4 hover:shadow-md cursor-pointer transition-shadow" onClick={() => handleViewTrace(ex)}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">{ex.objective.substring(0, 120)}{ex.objective.length > 120 ? '...' : ''}</span>
                {renderStatusBadge(ex.status)}
              </div>

              {/* Agent task progress */}
              {ex.tasks && ex.tasks.length > 0 && (
                <div className="mb-3">
                  <div className="flex gap-2 flex-wrap">
                    {ex.tasks.map(task => {
                      const agentInfo = agents.find(a => a.id === task.agent_id);
                      return (
                        <div key={task.id} className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${STATUS_COLORS[task.status] || 'bg-gray-100'}`}>
                          <span>{TASK_ICONS[task.status] || '?'}</span>
                          <span>{agentInfo?.name || task.agent_id.substring(0, 8)}</span>
                          {task.confidence !== null && <span className="text-gray-500">({Math.round((task.confidence || 0) * 100)}%)</span>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{ex.total_agent_tasks} agent{ex.total_agent_tasks !== 1 ? 's' : ''}</span>
                {ex.final_confidence !== null && <span>Confidence: {renderConfidence(ex.final_confidence)}</span>}
                {ex.conflicts && ex.conflicts.length > 0 && (
                  <span className="text-amber-600">{ex.conflicts.length} conflict{ex.conflicts.length !== 1 ? 's' : ''}</span>
                )}
                <span>{ex.total_token_usage.toLocaleString()} tokens</span>
                <span>{ex.created_at ? new Date(ex.created_at).toLocaleString() : ''}</span>
              </div>

              {ex.final_summary && (
                <p className="mt-2 text-sm text-gray-600 border-t pt-2">{ex.final_summary.substring(0, 200)}{ex.final_summary.length > 200 ? '...' : ''}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // --- Trace tab ---
  const renderTrace = () => {
    if (!selectedExecution) return <p className="text-gray-500">Select an execution to view its trace.</p>;

    return (
      <div className="space-y-6">
        <button onClick={() => { setTab('executions'); setSelectedExecution(null); setExecutionTrace(null); }} className="text-blue-600 text-sm hover:underline">&larr; Back to Executions</button>

        {/* Header */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">Execution Trace</h2>
            {renderStatusBadge(selectedExecution.status)}
          </div>
          <p className="text-gray-600 mb-3">{selectedExecution.objective}</p>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>Agents: {selectedExecution.total_agent_tasks}</span>
            <span>Confidence: {renderConfidence(selectedExecution.final_confidence)}</span>
            <span>Tokens: {selectedExecution.total_token_usage.toLocaleString()}</span>
            {selectedExecution.started_at && <span>Started: {new Date(selectedExecution.started_at).toLocaleString()}</span>}
          </div>
        </div>

        {/* Execution Flow */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h3 className="font-semibold mb-4">Execution Flow</h3>
          <div className="space-y-1">
            {/* Plan phase */}
            <div className="flex items-center gap-3 p-2 rounded bg-blue-50">
              <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs">1</span>
              <span className="text-sm font-medium">Planning</span>
              <span className="text-xs text-gray-500">{(selectedExecution.plan as Record<string, unknown>)?.plan_name as string || ''}</span>
            </div>

            {/* Agent tasks */}
            {(executionTrace?.tasks || selectedExecution.tasks || []).map((task, i) => {
              const agentInfo = agents.find(a => a.id === task.agent_id);
              return (
                <div key={task.id || task.task_id} className="ml-6 border-l-2 border-gray-200 pl-4">
                  <div className={`flex items-center gap-3 p-2 rounded ${STATUS_COLORS[task.status] || 'bg-gray-50'}`}>
                    <span className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center text-xs">{TASK_ICONS[task.status] || '?'}</span>
                    <span className="text-sm font-medium">{agentInfo?.name || `Agent ${task.agent_id?.substring(0, 8)}`}</span>
                    <span className="text-xs text-gray-500">{task.objective?.substring(0, 80)}</span>
                    {task.confidence !== null && <span className="ml-auto text-xs">{renderConfidence(task.confidence)}</span>}
                  </div>
                  {task.summary && <p className="text-xs text-gray-600 mt-1 ml-9">{task.summary}</p>}
                  {task.error && <p className="text-xs text-red-600 mt-1 ml-9">Error: {task.error}</p>}
                </div>
              );
            })}

            {/* Conflict resolution */}
            {selectedExecution.conflicts && selectedExecution.conflicts.length > 0 && (
              <div className="flex items-center gap-3 p-2 rounded bg-amber-50 mt-2">
                <span className="w-6 h-6 rounded-full bg-amber-500 text-white flex items-center justify-center text-xs">!</span>
                <span className="text-sm font-medium">Conflict Resolution</span>
                <span className="text-xs text-amber-600">{selectedExecution.conflicts.length} conflict(s)</span>
              </div>
            )}

            {/* Final result */}
            <div className={`flex items-center gap-3 p-2 rounded mt-2 ${STATUS_COLORS[selectedExecution.status] || 'bg-gray-50'}`}>
              <span className="w-6 h-6 rounded-full bg-green-600 text-white flex items-center justify-center text-xs">{TASK_ICONS[selectedExecution.status] || '?'}</span>
              <span className="text-sm font-medium">Final Result</span>
              <span className="ml-auto text-xs">{renderConfidence(selectedExecution.final_confidence)}</span>
            </div>
          </div>
        </div>

        {/* Final Summary */}
        {selectedExecution.final_summary && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="font-semibold mb-3">Summary</h3>
            <p className="text-gray-700 whitespace-pre-wrap">{selectedExecution.final_summary}</p>
          </div>
        )}

        {/* Final Recommendation */}
        {selectedExecution.final_recommendation && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="font-semibold mb-3">Recommendation</h3>
            <div className="space-y-2">
              <p className="font-medium">{(selectedExecution.final_recommendation as Record<string, string>).title}</p>
              <p className="text-gray-600">{(selectedExecution.final_recommendation as Record<string, string>).description}</p>
              {(selectedExecution.final_recommendation as Record<string, string>).rationale && (
                <p className="text-sm text-gray-500"><span className="font-medium">Rationale:</span> {(selectedExecution.final_recommendation as Record<string, string>).rationale}</p>
              )}
            </div>
          </div>
        )}

        {/* Conflicts */}
        {selectedExecution.conflicts && selectedExecution.conflicts.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="font-semibold mb-3">Conflicts Detected</h3>
            <div className="space-y-3">
              {selectedExecution.conflicts.map((conflict, i) => (
                <div key={i} className="border rounded p-3 bg-amber-50">
                  <div className="font-medium text-sm">{(conflict as Record<string, string>).topic}</div>
                  <div className="text-xs text-gray-500">Agents: {((conflict as Record<string, string[]>).agents || []).join(', ')}</div>
                  <div className="text-xs text-amber-600">Severity: {(conflict as Record<string, string>).severity}</div>
                </div>
              ))}
            </div>
            {selectedExecution.conflict_resolution && (
              <div className="mt-3 p-3 bg-green-50 rounded border border-green-200">
                <div className="text-sm font-medium text-green-700">Resolution Strategy: {(selectedExecution.conflict_resolution as Record<string, string>).strategy}</div>
              </div>
            )}
          </div>
        )}

        {/* Audit Timeline */}
        {executionTrace?.audit_timeline && executionTrace.audit_timeline.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="font-semibold mb-3">Audit Trail</h3>
            <div className="space-y-1">
              {executionTrace.audit_timeline.map((entry, i) => (
                <div key={i} className="flex items-center gap-3 text-sm py-1 border-b last:border-0">
                  <span className="text-xs text-gray-400 w-24">{entry.created_at ? new Date(entry.created_at).toLocaleTimeString() : ''}</span>
                  <span className="text-gray-700">{entry.action.replace(/_/g, ' ')}</span>
                  {entry.agent_name && <span className="text-xs text-blue-600">{entry.agent_name}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Cost Summary */}
        {executionTrace?.cost && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="font-semibold mb-3">Cost Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xl font-bold">{executionTrace.cost.total_agent_tasks}</div>
                <div className="text-xs text-gray-500">Agent Tasks</div>
              </div>
              <div>
                <div className="text-xl font-bold">{executionTrace.cost.total_llm_calls}</div>
                <div className="text-xs text-gray-500">LLM Calls</div>
              </div>
              <div>
                <div className="text-xl font-bold">{executionTrace.cost.total_tool_calls}</div>
                <div className="text-xs text-gray-500">Tool Calls</div>
              </div>
              <div>
                <div className="text-xl font-bold">{executionTrace.cost.total_token_usage.toLocaleString()}</div>
                <div className="text-xs text-gray-500">Tokens</div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // --- Metrics tab ---
  const renderMetrics = () => (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Agent Performance Metrics</h2>
      {agentMetrics.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border p-8 text-center text-gray-500">No metrics data available.</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {agentMetrics.map(m => (
            <div key={m.agent_id} className="bg-white rounded-xl shadow-sm border p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{AGENT_TYPE_ICONS[m.agent_type] || '\uD83E\uDD16'}</span>
                  <span className="font-semibold">{m.name}</span>
                  {renderStatusBadge(m.status)}
                </div>
                <span className="text-xs text-gray-400">v{m.version}</span>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="text-2xl font-bold text-blue-600">{m.tasks_total}</div>
                  <div className="text-xs text-gray-500">Total Tasks</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-600">{m.success_rate}%</div>
                  <div className="text-xs text-gray-500">Success Rate</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-amber-600">{m.avg_confidence}</div>
                  <div className="text-xs text-gray-500">Avg Confidence</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Completed</span>
                  <span className="text-green-600 font-medium">{m.tasks_completed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Failed</span>
                  <span className="text-red-600 font-medium">{m.tasks_failed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Timed Out</span>
                  <span className="text-amber-600 font-medium">{m.tasks_timed_out}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Avg Latency</span>
                  <span className="font-medium">{m.avg_latency_seconds}s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tokens</span>
                  <span className="font-medium">{m.total_token_usage.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">LLM Calls</span>
                  <span className="font-medium">{m.total_llm_calls}</span>
                </div>
              </div>

              <div className="mt-3 text-xs text-gray-400">
                Risk: {renderRiskBadge(m.risk_level)}
                {m.last_activity && <span className="ml-3">Last active: {new Date(m.last_activity).toLocaleString()}</span>}
              </div>

              {/* Success rate bar */}
              <div className="mt-3">
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${m.success_rate}%` }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  // --- Execute Modal ---
  const renderExecuteModal = () => {
    if (!showExecute) return null;
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">New Multi-Agent Orchestration</h2>
            <button onClick={() => { setShowExecute(false); setExecutePlan(null); setError(null); }} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Business Objective</label>
              <textarea
                className="w-full border rounded-lg p-3 text-sm min-h-[80px] focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g., Find ways to reduce our operating expenses by 10%"
                value={executeObjective}
                onChange={e => setExecuteObjective(e.target.value)}
              />
            </div>

            {/* Plan preview */}
            {executePlan && (
              <div className="border rounded-lg p-4 bg-blue-50">
                <h3 className="font-medium text-sm mb-2">Execution Plan</h3>
                <p className="text-sm text-gray-600 mb-2">{(executePlan as Record<string, string>).plan_description}</p>
                <div className="space-y-1">
                  {((executePlan as Record<string, Array<Record<string, unknown>>>).tasks || []).map((task, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="text-blue-600">{AGENT_TYPE_ICONS[(task.agent_type as string)] || '\uD83E\uDD16'}</span>
                      <span className="font-medium">{task.agent_type as string}</span>
                      <span className="text-gray-500">— {(task.objective as string)?.substring(0, 80)}</span>
                    </div>
                  ))}
                </div>
                {(executePlan as Record<string, string[]>).warnings && ((executePlan as Record<string, string[]>).warnings).length > 0 && (
                  <div className="mt-2 text-xs text-amber-600">
                    {((executePlan as Record<string, string[]>).warnings).map((w, i) => <div key={i}>⚠ {w}</div>)}
                  </div>
                )}
              </div>
            )}

            {error && <div className="text-red-600 text-sm bg-red-50 rounded p-2">{error}</div>}

            <div className="flex gap-2">
              <button
                onClick={handleCreatePlan}
                disabled={planning || !executeObjective.trim()}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 disabled:opacity-50"
              >
                {planning ? 'Planning...' : 'Preview Plan'}
              </button>
              <button
                onClick={handleExecute}
                disabled={executing || !executeObjective.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {executing ? 'Executing...' : 'Execute'}
              </button>
            </div>

            {/* Example scenarios */}
            <div className="border-t pt-3">
              <p className="text-xs text-gray-500 mb-2">Try one of these:</p>
              <div className="flex flex-wrap gap-2">
                {[
                  'Find ways to reduce our operating expenses by 10%',
                  'Which customers are at risk of leaving?',
                  'Should we renew the contract with Vendor X?',
                ].map(example => (
                  <button
                    key={example}
                    onClick={() => setExecuteObjective(example)}
                    className="px-2 py-1 text-xs bg-gray-100 rounded hover:bg-gray-200"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // --- Main layout ---
  const tabs: { id: Tab; label: string }[] = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'agents', label: 'Agents' },
    { id: 'executions', label: 'Orchestrations' },
    { id: 'trace', label: 'Execution Trace' },
    { id: 'metrics', label: 'Metrics' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Multi-Agent Orchestration</h1>
            <p className="text-gray-500 text-sm">Coordinate specialized agents to solve complex business problems</p>
          </div>
          <button onClick={() => setShowExecute(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 font-medium">
            New Orchestration
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-white rounded-lg p-1 shadow-sm border mb-6">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === t.id ? 'bg-blue-600 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : (
          <>
            {tab === 'dashboard' && renderDashboard()}
            {tab === 'agents' && renderAgents()}
            {tab === 'executions' && renderExecutions()}
            {tab === 'trace' && renderTrace()}
            {tab === 'metrics' && renderMetrics()}
          </>
        )}

        {renderExecuteModal()}
      </div>
    </div>
  );
}
