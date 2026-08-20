'use client';

import { useEffect, useState } from 'react';

interface Workflow {
  id: string;
  name: string;
  description: string | null;
  trigger: string | null;
  status: string;
  is_template: boolean;
  template_category: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface Execution {
  id: string;
  workflow_id: string;
  status: string;
  objective: string | null;
  progress: number;
  completed_steps: number;
  total_steps: number;
  total_tool_calls: number;
  total_llm_calls: number;
  total_token_usage: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  steps: StepExecution[];
  approvals: Approval[];
}

interface StepExecution {
  id: string;
  step_index: number;
  step_name: string;
  step_type: string;
  status: string;
  tool_name: string | null;
  risk_level: string | null;
  requires_approval: boolean;
  error: string | null;
  reasoning: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface Approval {
  id: string;
  execution_id: string;
  step_execution_id: string | null;
  status: string;
  action_type: string;
  action_description: string;
  action_parameters: Record<string, unknown> | null;
  risk_level: string;
  reason: string | null;
  target_system: string | null;
  expected_outcome: string | null;
  expires_at: string | null;
  created_at: string | null;
}

interface Template {
  name: string;
  description: string;
  trigger: string;
  template_category: string;
  steps: Array<{ name: string; description: string }>;
}

interface Metrics {
  total_executions_started: number;
  total_executions_completed: number;
  total_executions_failed: number;
  success_rate: number;
  failure_rate: number;
  approvals_requested: number;
  approvals_granted: number;
  approvals_rejected: number;
  tools_executed: number;
  tool_failures: number;
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-600',
  active: 'bg-green-50 text-green-700',
  inactive: 'bg-yellow-50 text-yellow-700',
  planned: 'bg-blue-50 text-blue-700',
  running: 'bg-blue-50 text-blue-700',
  completed: 'bg-green-50 text-green-700',
  failed: 'bg-red-50 text-red-700',
  cancelled: 'bg-slate-100 text-slate-600',
  paused: 'bg-amber-50 text-amber-700',
  waiting_for_approval: 'bg-orange-50 text-orange-700',
  waiting_for_input: 'bg-purple-50 text-purple-700',
  pending: 'bg-yellow-50 text-yellow-700',
  approved: 'bg-green-50 text-green-700',
  rejected: 'bg-red-50 text-red-700',
};

const STEP_ICONS: Record<string, string> = {
  completed: '\u2713',
  failed: '\u2717',
  running: '\u25B6',
  pending: '\u25CB',
  skipped: '\u2014',
  waiting_for_approval: '\u26A0',
  cancelled: '\u2014',
};

const RISK_COLORS: Record<string, string> = {
  low: 'text-green-600',
  medium: 'text-amber-600',
  high: 'text-red-600',
  critical: 'text-red-700 font-bold',
};

type Tab = 'dashboard' | 'workflows' | 'executions' | 'templates' | 'builder' | 'metrics';

export default function WorkflowsPage() {
  const [tab, setTab] = useState<Tab>('dashboard');
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<Execution | null>(null);
  const [loading, setLoading] = useState(true);

  // Builder state
  const [builderName, setBuilderName] = useState('');
  const [builderDesc, setBuilderDesc] = useState('');
  const [builderTrigger, setBuilderTrigger] = useState('');
  const [builderSteps, setBuilderSteps] = useState<Array<{ name: string; tool: string; description: string; requires_approval: boolean }>>([]);

  // Execute modal
  const [showExecute, setShowExecute] = useState<string | null>(null);
  const [executeObjective, setExecuteObjective] = useState('');
  const [executeInputs, setExecuteInputs] = useState('{}');

  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

  const fetchWorkflows = async () => {
    try {
      const res = await fetch('/api/workflows', { headers: headers() });
      if (res.ok) { const d = await res.json(); setWorkflows(d.workflows); }
    } catch {}
  };

  const fetchExecutions = async () => {
    try {
      const res = await fetch('/api/workflows/executions/list', { headers: headers() });
      if (res.ok) { const d = await res.json(); setExecutions(d.executions); }
    } catch {}
  };

  const fetchTemplates = async () => {
    try {
      const res = await fetch('/api/workflows/templates', { headers: headers() });
      if (res.ok) { const d = await res.json(); setTemplates(d.templates); }
    } catch {}
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/workflows/metrics/overview', { headers: headers() });
      if (res.ok) { setMetrics(await res.json()); }
    } catch {}
  };

  const fetchAll = async () => {
    setLoading(true);
    await Promise.all([fetchWorkflows(), fetchExecutions(), fetchTemplates(), fetchMetrics()]);
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  // Actions
  const handleExecute = async (workflowId: string) => {
    try {
      let parsedInputs = {};
      try { parsedInputs = JSON.parse(executeInputs); } catch {}
      const res = await fetch(`/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ inputs: parsedInputs, objective: executeObjective || null }),
      });
      if (res.ok) {
        setShowExecute(null);
        setExecuteObjective('');
        setExecuteInputs('{}');
        fetchExecutions();
      }
    } catch {}
  };

  const handleApprove = async (executionId: string, approvalId: string) => {
    try {
      await fetch(`/api/workflows/executions/${executionId}/approve?approval_id=${approvalId}`, {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      fetchExecutions();
      if (selectedExecution?.id === executionId) {
        const res = await fetch(`/api/workflows/executions/${executionId}`, { headers: headers() });
        if (res.ok) setSelectedExecution(await res.json());
      }
    } catch {}
  };

  const handleReject = async (executionId: string, approvalId: string) => {
    try {
      await fetch(`/api/workflows/executions/${executionId}/reject?approval_id=${approvalId}`, {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_note: 'Rejected by user' }),
      });
      fetchExecutions();
    } catch {}
  };

  const handleResume = async (workflowId: string, executionId: string) => {
    try {
      await fetch(`/api/workflows/${workflowId}/resume?execution_id=${executionId}`, {
        method: 'POST',
        headers: headers(),
      });
      fetchExecutions();
    } catch {}
  };

  const handleCancel = async (workflowId: string, executionId: string) => {
    if (!confirm('Cancel this workflow execution?')) return;
    try {
      await fetch(`/api/workflows/${workflowId}/cancel?execution_id=${executionId}`, {
        method: 'POST',
        headers: headers(),
      });
      fetchExecutions();
    } catch {}
  };

  const handleCreateWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/workflows', {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: builderName,
          description: builderDesc,
          trigger: builderTrigger || null,
          steps: builderSteps.map((s, i) => ({
            index: i,
            name: s.name,
            description: s.description,
            type: s.requires_approval ? 'approval' : 'action',
            tool: s.tool || null,
            requires_approval: s.requires_approval,
            risk_level: s.requires_approval ? 'medium' : 'low',
          })),
        }),
      });
      if (res.ok) {
        setBuilderName('');
        setBuilderDesc('');
        setBuilderTrigger('');
        setBuilderSteps([]);
        setTab('workflows');
        fetchWorkflows();
      }
    } catch {}
  };

  const handleCreateFromTemplate = async (templateName: string) => {
    try {
      const res = await fetch('/api/workflows/from-template', {
        method: 'POST',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_name: templateName }),
      });
      if (res.ok) {
        setTab('workflows');
        fetchWorkflows();
      }
    } catch {}
  };

  const handleActivate = async (workflowId: string) => {
    try {
      await fetch(`/api/workflows/${workflowId}`, {
        method: 'PATCH',
        headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'active' }),
      });
      fetchWorkflows();
    } catch {}
  };

  const addBuilderStep = () => {
    setBuilderSteps([...builderSteps, { name: '', tool: '', description: '', requires_approval: false }]);
  };

  const updateBuilderStep = (idx: number, field: string, value: string | boolean) => {
    const updated = [...builderSteps];
    (updated[idx] as Record<string, string | boolean>)[field] = value;
    setBuilderSteps(updated);
  };

  const removeBuilderStep = (idx: number) => {
    setBuilderSteps(builderSteps.filter((_, i) => i !== idx));
  };

  // Active/pending counts
  const activeExecs = executions.filter(e => e.status === 'running').length;
  const waitingApproval = executions.filter(e => e.status === 'waiting_for_approval').length;
  const completedExecs = executions.filter(e => e.status === 'completed').length;
  const failedExecs = executions.filter(e => e.status === 'failed').length;

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-12">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-slate-900">Autonomous Workflows</h1>
        <p className="mt-1 text-slate-500">Build, execute, and monitor business workflows with AI-powered planning</p>
      </div>

      {/* Tab Navigation */}
      <div className="mb-6 flex gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
        {(['dashboard', 'workflows', 'executions', 'templates', 'builder', 'metrics'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-2 text-sm font-medium capitalize transition-colors ${
              tab === t ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            {t}
            {t === 'executions' && waitingApproval > 0 && (
              <span className="ml-2 rounded-full bg-orange-500 px-2 py-0.5 text-xs text-white">{waitingApproval}</span>
            )}
          </button>
        ))}
      </div>

      {loading && <p className="text-slate-500">Loading...</p>}

      {/* ============ DASHBOARD TAB ============ */}
      {!loading && tab === 'dashboard' && (
        <div>
          {/* Status cards */}
          <div className="mb-8 grid grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Active</p>
              <p className="mt-1 text-3xl font-bold text-blue-600">{activeExecs}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Waiting Approval</p>
              <p className="mt-1 text-3xl font-bold text-orange-500">{waitingApproval}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Completed</p>
              <p className="mt-1 text-3xl font-bold text-green-600">{completedExecs}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Failed</p>
              <p className="mt-1 text-3xl font-bold text-red-500">{failedExecs}</p>
            </div>
          </div>

          {/* Pending approvals */}
          {executions.filter(e => e.status === 'waiting_for_approval').length > 0 && (
            <div className="mb-8">
              <h2 className="mb-4 text-xl font-semibold text-slate-900">Pending Approvals</h2>
              {executions
                .filter(e => e.status === 'waiting_for_approval')
                .map(exec => (
                  <div key={exec.id} className="mb-4 rounded-xl border border-orange-200 bg-orange-50 p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-slate-900">{exec.objective || `Execution ${exec.id.slice(0, 8)}`}</p>
                        <p className="text-sm text-slate-500">
                          Progress: {exec.completed_steps}/{exec.total_steps} steps
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs ${STATUS_COLORS.waiting_for_approval}`}>
                        Waiting for Approval
                      </span>
                    </div>
                    {exec.approvals
                      .filter(a => a.status === 'pending')
                      .map(approval => (
                        <div key={approval.id} className="mt-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                          <p className="mb-1 text-sm font-medium text-orange-600">Approval Required</p>
                          <p className="mb-2 text-slate-800">{approval.action_description}</p>
                          <div className="mb-3 flex gap-4 text-sm text-slate-500">
                            <span>Risk: <span className={RISK_COLORS[approval.risk_level] || ''}>{approval.risk_level}</span></span>
                            {approval.target_system && <span>Target: {approval.target_system}</span>}
                          </div>
                          {approval.expected_outcome && (
                            <p className="mb-3 text-sm text-slate-500">Expected: {approval.expected_outcome}</p>
                          )}
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleApprove(exec.id, approval.id)}
                              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(exec.id, approval.id)}
                              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      ))}
                  </div>
                ))}
            </div>
          )}

          {/* Active executions */}
          {executions.filter(e => e.status === 'running').length > 0 && (
            <div>
              <h2 className="mb-4 text-xl font-semibold text-slate-900">Active Executions</h2>
              {executions
                .filter(e => e.status === 'running')
                .map(exec => (
                  <div key={exec.id} className="mb-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-slate-900">{exec.objective || `Execution ${exec.id.slice(0, 8)}`}</p>
                      <span className={`rounded-full px-3 py-1 text-xs ${STATUS_COLORS.running}`}>Running</span>
                    </div>
                    <div className="mt-3">
                      <div className="h-2 rounded-full bg-slate-200">
                        <div className="h-2 rounded-full bg-blue-500 transition-all" style={{ width: `${exec.progress}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{exec.progress}% — {exec.completed_steps}/{exec.total_steps} steps</p>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* ============ WORKFLOWS TAB ============ */}
      {!loading && tab === 'workflows' && (
        <div>
          <div className="mb-4 flex justify-end gap-3">
            <button onClick={() => setTab('builder')} className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-4 py-2 text-sm font-medium text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all">
              + New Workflow
            </button>
          </div>

          {workflows.length === 0 && <p className="text-slate-500">No workflows yet. Create one or use a template.</p>}

          <div className="space-y-3">
            {workflows.map(wf => (
              <div key={wf.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-slate-900">{wf.name}</p>
                    {wf.description && <p className="mt-1 text-sm text-slate-500">{wf.description}</p>}
                    {wf.trigger && <p className="mt-1 text-xs text-slate-400">Trigger: {wf.trigger}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-3 py-1 text-xs ${STATUS_COLORS[wf.status] || STATUS_COLORS.draft}`}>
                      {wf.status}
                    </span>
                    {wf.status === 'draft' && (
                      <button onClick={() => handleActivate(wf.id)} className="rounded-lg border border-green-300 px-3 py-1 text-xs text-green-700 hover:bg-green-50">
                        Activate
                      </button>
                    )}
                    <button
                      onClick={() => { setShowExecute(wf.id); setExecuteObjective(''); setExecuteInputs('{}'); }}
                      className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-3 py-1 text-xs font-medium text-white hover:shadow-md transition-all"
                    >
                      Execute
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============ EXECUTIONS TAB ============ */}
      {!loading && tab === 'executions' && !selectedExecution && (
        <div>
          {executions.length === 0 && <p className="text-slate-500">No executions yet.</p>}
          <div className="space-y-3">
            {executions.map(exec => (
              <div
                key={exec.id}
                onClick={() => setSelectedExecution(exec)}
                className="cursor-pointer rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-300 hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-slate-900">{exec.objective || `Execution ${exec.id.slice(0, 8)}`}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Started: {exec.started_at ? new Date(exec.started_at).toLocaleString() : 'Not started'}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`rounded-full px-3 py-1 text-xs ${STATUS_COLORS[exec.status] || ''}`}>
                      {exec.status.replace(/_/g, ' ')}
                    </span>
                    <span className="text-sm text-slate-500">{exec.progress}%</span>
                  </div>
                </div>
                {/* Progress bar */}
                <div className="mt-3 h-1.5 rounded-full bg-slate-200">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      exec.status === 'completed' ? 'bg-green-500' :
                      exec.status === 'failed' ? 'bg-red-500' :
                      exec.status === 'waiting_for_approval' ? 'bg-orange-500' : 'bg-blue-500'
                    }`}
                    style={{ width: `${exec.progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============ EXECUTION DETAIL VIEW ============ */}
      {!loading && tab === 'executions' && selectedExecution && (
        <div>
          <button onClick={() => setSelectedExecution(null)} className="mb-4 text-sm text-blue-600 hover:underline">
            &larr; Back to list
          </button>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">
                  {selectedExecution.objective || `Execution ${selectedExecution.id.slice(0, 8)}`}
                </h2>
                <p className="text-sm text-slate-500">
                  {selectedExecution.started_at && `Started: ${new Date(selectedExecution.started_at).toLocaleString()}`}
                  {selectedExecution.completed_at && ` — Completed: ${new Date(selectedExecution.completed_at).toLocaleString()}`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-3 py-1 text-xs ${STATUS_COLORS[selectedExecution.status] || ''}`}>
                  {selectedExecution.status.replace(/_/g, ' ')}
                </span>
                {['running', 'waiting_for_approval'].includes(selectedExecution.status) && (
                  <button
                    onClick={() => handleCancel(selectedExecution.workflow_id, selectedExecution.id)}
                    className="rounded-lg border border-red-300 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
                  >
                    Cancel
                  </button>
                )}
                {['paused', 'failed'].includes(selectedExecution.status) && (
                  <button
                    onClick={() => handleResume(selectedExecution.workflow_id, selectedExecution.id)}
                    className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-3 py-1 text-xs font-medium text-white hover:shadow-md transition-all"
                  >
                    Resume
                  </button>
                )}
              </div>
            </div>

            {/* Progress */}
            <div className="mb-6">
              <div className="h-3 rounded-full bg-slate-200">
                <div
                  className={`h-3 rounded-full transition-all ${
                    selectedExecution.status === 'completed' ? 'bg-green-500' :
                    selectedExecution.status === 'failed' ? 'bg-red-500' :
                    selectedExecution.status === 'waiting_for_approval' ? 'bg-orange-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${selectedExecution.progress}%` }}
                />
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {selectedExecution.completed_steps} / {selectedExecution.total_steps} steps completed ({selectedExecution.progress}%)
              </p>
            </div>

            {/* Error */}
            {selectedExecution.error && (
              <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
                <p className="text-sm font-medium text-red-700">Error</p>
                <p className="mt-1 text-sm text-red-600">{selectedExecution.error}</p>
              </div>
            )}

            {/* Steps timeline */}
            <h3 className="mb-3 text-lg font-medium text-slate-900">Steps</h3>
            <div className="space-y-2">
              {selectedExecution.steps.map(step => (
                <div key={step.id} className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <span className={`mt-0.5 text-lg ${
                    step.status === 'completed' ? 'text-green-600' :
                    step.status === 'failed' ? 'text-red-600' :
                    step.status === 'running' ? 'text-blue-600' :
                    step.status === 'waiting_for_approval' ? 'text-orange-500' : 'text-slate-400'
                  }`}>
                    {STEP_ICONS[step.status] || '\u25CB'}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-slate-900">{step.step_name}</p>
                      <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLORS[step.status] || ''}`}>
                        {step.status.replace(/_/g, ' ')}
                      </span>
                      {step.risk_level && (
                        <span className={`text-xs ${RISK_COLORS[step.risk_level] || ''}`}>
                          {step.risk_level} risk
                        </span>
                      )}
                    </div>
                    {step.reasoning && <p className="mt-1 text-sm text-slate-500">{step.reasoning}</p>}
                    {step.tool_name && <p className="mt-1 text-xs text-slate-400">Tool: {step.tool_name}</p>}
                    {step.error && <p className="mt-1 text-sm text-red-600">{step.error}</p>}
                    {step.started_at && (
                      <p className="mt-1 text-xs text-slate-400">
                        {new Date(step.started_at).toLocaleTimeString()}
                        {step.completed_at && ` — ${new Date(step.completed_at).toLocaleTimeString()}`}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Pending approvals */}
            {selectedExecution.approvals.filter(a => a.status === 'pending').length > 0 && (
              <div className="mt-6">
                <h3 className="mb-3 text-lg font-medium text-orange-600">Approval Required</h3>
                {selectedExecution.approvals
                  .filter(a => a.status === 'pending')
                  .map(approval => (
                    <div key={approval.id} className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                      <p className="mb-1 text-slate-800">{approval.action_description}</p>
                      <div className="mb-3 flex gap-4 text-sm text-slate-500">
                        <span>Risk: <span className={RISK_COLORS[approval.risk_level] || ''}>{approval.risk_level}</span></span>
                        {approval.target_system && <span>Target: {approval.target_system}</span>}
                        {approval.expected_outcome && <span>Expected: {approval.expected_outcome}</span>}
                      </div>
                      {approval.action_parameters && (
                        <pre className="mb-3 rounded bg-slate-100 p-2 text-xs text-slate-700">{JSON.stringify(approval.action_parameters, null, 2)}</pre>
                      )}
                      <div className="flex gap-2">
                        <button onClick={() => handleApprove(selectedExecution.id, approval.id)} className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500">Approve</button>
                        <button onClick={() => handleReject(selectedExecution.id, approval.id)} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500">Reject</button>
                      </div>
                    </div>
                  ))}
              </div>
            )}

            {/* Cost tracking */}
            <div className="mt-6 flex gap-6 text-sm text-slate-500">
              <span>Tool calls: {selectedExecution.total_tool_calls}</span>
              <span>LLM calls: {selectedExecution.total_llm_calls}</span>
              <span>Tokens: {selectedExecution.total_token_usage.toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}

      {/* ============ TEMPLATES TAB ============ */}
      {!loading && tab === 'templates' && (
        <div className="space-y-4">
          {templates.map(tmpl => (
            <div key={tmpl.name} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-slate-900">{tmpl.name}</p>
                  <p className="mt-1 text-sm text-slate-500">{tmpl.description}</p>
                  <div className="mt-2 flex gap-2">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{tmpl.template_category}</span>
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{tmpl.steps?.length || 0} steps</span>
                  </div>
                </div>
                <button
                  onClick={() => handleCreateFromTemplate(tmpl.name)}
                  className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-4 py-2 text-sm font-medium text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all"
                >
                  Use Template
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ============ BUILDER TAB ============ */}
      {!loading && tab === 'builder' && (
        <form onSubmit={handleCreateWorkflow} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold text-slate-900">Workflow Builder</h2>

          <div className="mb-4">
            <label className="mb-1 block text-sm text-slate-500">Workflow Name</label>
            <input type="text" value={builderName} onChange={e => setBuilderName(e.target.value)} required
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="e.g. Customer Onboarding" />
          </div>

          <div className="mb-4">
            <label className="mb-1 block text-sm text-slate-500">Description</label>
            <textarea value={builderDesc} onChange={e => setBuilderDesc(e.target.value)} rows={2}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="What does this workflow do?" />
          </div>

          <div className="mb-4">
            <label className="mb-1 block text-sm text-slate-500">Trigger (optional)</label>
            <input type="text" value={builderTrigger} onChange={e => setBuilderTrigger(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="e.g. new_customer, overdue_invoice" />
          </div>

          <div className="mb-4">
            <div className="mb-2 flex items-center justify-between">
              <label className="text-sm text-slate-500">Steps</label>
              <button type="button" onClick={addBuilderStep}
                className="rounded-lg border border-blue-300 px-3 py-1 text-xs text-blue-600 hover:bg-blue-50">
                + Add Step
              </button>
            </div>

            {builderSteps.map((step, idx) => (
              <div key={idx} className="mb-2 flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex-1 space-y-2">
                  <input type="text" value={step.name} onChange={e => updateBuilderStep(idx, 'name', e.target.value)}
                    placeholder="Step name" className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-800" />
                  <input type="text" value={step.description} onChange={e => updateBuilderStep(idx, 'description', e.target.value)}
                    placeholder="Description" className="w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-800" />
                  <div className="flex gap-2">
                    <input type="text" value={step.tool} onChange={e => updateBuilderStep(idx, 'tool', e.target.value)}
                      placeholder="Tool name (optional)" className="flex-1 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-800" />
                    <label className="flex items-center gap-1 text-xs text-slate-500">
                      <input type="checkbox" checked={step.requires_approval}
                        onChange={e => updateBuilderStep(idx, 'requires_approval', e.target.checked)} />
                      Requires Approval
                    </label>
                  </div>
                </div>
                <button type="button" onClick={() => removeBuilderStep(idx)}
                className="text-red-500 hover:text-red-600">&times;</button>
              </div>
            ))}
          </div>

          <button type="submit" className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-6 py-2 font-medium text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all">
            Create Workflow
          </button>
        </form>
      )}

      {/* ============ METRICS TAB ============ */}
      {!loading && tab === 'metrics' && metrics && (
        <div>
          <div className="mb-6 grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Success Rate</p>
              <p className="mt-1 text-3xl font-bold text-green-600">{metrics.success_rate.toFixed(1)}%</p>
              <p className="mt-1 text-xs text-slate-400">{metrics.total_executions_completed} / {metrics.total_executions_started} executions</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Failure Rate</p>
              <p className="mt-1 text-3xl font-bold text-red-500">{metrics.failure_rate.toFixed(1)}%</p>
              <p className="mt-1 text-xs text-slate-400">{metrics.total_executions_failed} failed</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Approval Rate</p>
              <p className="mt-1 text-3xl font-bold text-purple-600">
                {metrics.approvals_requested > 0 ? ((metrics.approvals_granted / metrics.approvals_requested) * 100).toFixed(1) : 0}%
              </p>
              <p className="mt-1 text-xs text-slate-400">{metrics.approvals_granted} / {metrics.approvals_requested} approved</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="mb-3 text-sm font-medium text-slate-900">Execution Summary</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">Total Started</span><span className="text-slate-900">{metrics.total_executions_started}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Completed</span><span className="text-green-600">{metrics.total_executions_completed}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Failed</span><span className="text-red-600">{metrics.total_executions_failed}</span></div>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="mb-3 text-sm font-medium text-slate-900">Tool Execution</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">Tools Executed</span><span className="text-slate-900">{metrics.tools_executed}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Tool Failures</span><span className="text-red-600">{metrics.tool_failures}</span></div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Tool Failure Rate</span>
                  <span className="text-slate-900">{metrics.tools_executed > 0 ? ((metrics.tool_failures / metrics.tools_executed) * 100).toFixed(1) : 0}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============ EXECUTE MODAL ============ */}
      {showExecute && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-xl font-semibold text-slate-900">Execute Workflow</h2>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-500">Objective (optional — enables AI planning)</label>
              <textarea value={executeObjective} onChange={e => setExecuteObjective(e.target.value)} rows={3}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder="e.g. Find all overdue invoices over $5,000 and follow up" />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-500">Inputs (JSON)</label>
              <textarea value={executeInputs} onChange={e => setExecuteInputs(e.target.value)} rows={3}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                placeholder='{"customer_name": "Acme"}' />
            </div>
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setShowExecute(null)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-slate-600 hover:bg-slate-50">Cancel</button>
              <button type="button" onClick={() => handleExecute(showExecute)}
                className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-4 py-2 font-medium text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all">Execute</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
