'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface Scenario {
  id: string;
  name: string;
  description: string;
  icon: string;
  objective: string;
}

interface ScenarioResult {
  status: string;
  scenario: string;
  execution_id?: string;
  summary?: string;
  recommendation?: string;
  confidence?: number;
  message?: string;
  note?: string;
}

export default function ScenariosPage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [result, setResult] = useState<ScenarioResult | null>(null);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  async function fetchScenarios() {
    try {
      const res = await fetch('/api/business/scenarios');
      if (res.ok) {
        const data = await res.json();
        setScenarios(data.scenarios);
      }
    } catch {}
    setLoading(false);
  }

  async function runScenario(scenarioId: string) {
    if (!token) { router.push('/login'); return; }
    setRunningId(scenarioId);
    setResult(null);
    try {
      const res = await fetch('/api/business/scenarios/run', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
      }
    } catch (e) {
      setResult({ status: 'error', scenario: scenarioId, message: 'Failed to run scenario' });
    }
    setRunningId(null);
  }

  useEffect(() => { fetchScenarios(); }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      {/* Demo Mode Banner */}
      <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 flex items-center gap-3">
        <span className="text-amber-600 font-semibold text-sm">⚠️ DEMO MODE</span>
        <span className="text-amber-700 text-sm">These scenarios demonstrate AgentMason's multi-agent orchestration capabilities using demo data.</span>
      </div>

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">🎬 Demo Scenarios</h1>
        <p className="text-slate-500 text-sm mt-1">
          One-click demonstrations of AgentMason running real business operations
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-8">
        {loading ? (
          <div className="col-span-2 text-center py-12 text-slate-400">Loading scenarios...</div>
        ) : (
          scenarios.map((scenario) => (
            <div
              key={scenario.id}
              className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-all"
            >
              <div className="flex items-start gap-4">
                <span className="text-3xl">{scenario.icon}</span>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">{scenario.name}</h3>
                  <p className="text-sm text-slate-600 mb-3">{scenario.description}</p>
                  <details className="mb-4">
                    <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-600">What will AgentMason do?</summary>
                    <p className="text-xs text-slate-500 mt-2 bg-slate-50 rounded-lg p-3">{scenario.objective}</p>
                  </details>
                  <button
                    onClick={() => runScenario(scenario.id)}
                    disabled={runningId !== null}
                    className={`rounded-lg px-5 py-2.5 text-sm font-semibold transition-all ${
                      runningId === scenario.id
                        ? 'bg-slate-200 text-slate-500 cursor-wait'
                        : 'bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:shadow-lg hover:shadow-purple-500/25 disabled:opacity-50'
                    }`}
                  >
                    {runningId === scenario.id ? '⏳ Running...' : '▶ Run Scenario'}
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Result Panel */}
      {result && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className={`text-sm font-semibold px-3 py-1 rounded-full ${
              result.status === 'ok' ? 'bg-green-100 text-green-700' :
              result.status === 'demo_fallback' ? 'bg-amber-100 text-amber-700' :
              'bg-red-100 text-red-700'
            }`}>
              {result.status === 'ok' ? '✓ Completed' : result.status === 'demo_fallback' ? '⚠️ Demo Fallback' : '✕ Error'}
            </span>
            <h3 className="text-lg font-semibold text-slate-900">{result.scenario}</h3>
          </div>

          {result.summary && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Summary</h4>
              <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-4 whitespace-pre-wrap">{result.summary}</p>
            </div>
          )}

          {result.recommendation && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Recommendation</h4>
              <p className="text-sm text-blue-700 bg-blue-50 rounded-lg p-4 whitespace-pre-wrap">{result.recommendation}</p>
            </div>
          )}

          {result.confidence !== undefined && result.confidence !== null && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Confidence</h4>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden max-w-xs">
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${result.confidence * 100}%` }} />
                </div>
                <span className="text-sm font-medium text-slate-700">{(result.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}

          {result.message && (
            <div className="mb-4">
              <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-4">{result.message}</p>
            </div>
          )}

          {result.note && (
            <p className="text-xs text-slate-400 mt-2">{result.note}</p>
          )}

          {result.execution_id && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <button
                onClick={() => router.push(`/orchestration?execution=${result.execution_id}`)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                View Full Execution Trace →
              </button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
