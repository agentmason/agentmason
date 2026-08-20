'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface KPI {
  name: string;
  category: string;
  value: number;
  unit: string;
  target: number | null;
  trend: string | null;
  is_demo_data: boolean;
}

interface AttentionItem {
  id: string;
  category: string;
  priority: string;
  title: string;
  description: string;
  agent_name: string;
  requires_approval: boolean;
  is_demo_data: boolean;
}

interface Activity {
  id: string;
  agent_name: string;
  action: string;
  result: string;
  created_at: string;
  is_demo_data: boolean;
}

interface DashboardData {
  company_name: string;
  product_name: string;
  demo_mode: boolean;
  health: Record<string, KPI | null>;
  kpis: KPI[];
  attention_items: AttentionItem[];
  recent_activities: Activity[];
  summary: {
    total_kpis: number;
    open_attention_items: number;
    pending_approvals: number;
    opportunities: number;
    risks: number;
  };
}

interface BriefingData {
  company_name: string;
  demo_mode: boolean;
  greeting: string;
  top_priorities: { title: string; priority: string; category: string; why: string; action: string }[];
  risks: { title: string; description: string; evidence: string; risk: string }[];
  opportunities: { title: string; description: string; evidence: string; action: string }[];
  completed_recently: { agent_name: string; action: string; result: string }[];
  waiting_for_approval: { id: string; title: string; description: string; agent_name: string; risk: string }[];
  kpi_highlights: { name: string; value: number; target: number; unit: string; progress_pct: number; status: string; trend: string; is_demo_data: boolean }[];
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-green-100 text-green-800 border-green-200',
};

const PRIORITY_DOTS: Record<string, string> = {
  critical: '🔴',
  high: '🟠',
  medium: '🟡',
  low: '🟢',
};

const TREND_ICONS: Record<string, string> = {
  up: '↑',
  down: '↓',
  flat: '→',
};

const CATEGORY_COLORS: Record<string, string> = {
  revenue: 'text-emerald-600',
  sales: 'text-blue-600',
  finance: 'text-amber-600',
  product: 'text-purple-600',
  operations: 'text-cyan-600',
  government: 'text-rose-600',
  engineering: 'text-indigo-600',
};

export default function DashboardPage() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [showBriefing, setShowBriefing] = useState(false);
  const [error, setError] = useState('');
  const [askInput, setAskInput] = useState('');

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  async function fetchDashboard() {
    if (!token) { router.push('/login'); return; }
    try {
      const res = await fetch('/api/business/dashboard', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 404) {
        setError('not_seeded');
        setLoading(false);
        return;
      }
      if (!res.ok) throw new Error('Failed to fetch dashboard');
      const data = await res.json();
      setDashboard(data);
      setError('');
    } catch (e) {
      setError('Failed to load dashboard');
    }
    setLoading(false);
  }

  async function fetchBriefing() {
    if (!token) return;
    try {
      const res = await fetch('/api/business/briefing', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setBriefing(await res.json());
    } catch {}
  }

  async function seedBusiness() {
    if (!token) return;
    setSeeding(true);
    try {
      const res = await fetch('/api/business/seed', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: false }),
      });
      if (res.ok) {
        setError('');
        await fetchDashboard();
        await fetchBriefing();
      }
    } catch {}
    setSeeding(false);
  }

  async function handleAsk() {
    if (!askInput.trim() || !token) return;
    // Route to orchestration with the objective
    const encoded = encodeURIComponent(askInput);
    router.push(`/orchestration?objective=${encoded}`);
  }

  useEffect(() => {
    fetchDashboard();
    fetchBriefing();
  }, []);

  // ── Not seeded ───────────────────────────────────────────────────
  if (error === 'not_seeded') {
    return (
      <main className="mx-auto max-w-4xl px-6 py-20 text-center">
        <h1 className="text-3xl font-bold text-slate-900 mb-4">Welcome to AgentMason</h1>
        <p className="text-slate-600 mb-8">Your business workspace hasn't been configured yet. Click below to set up the dogfood demo environment.</p>
        <button
          onClick={seedBusiness}
          disabled={seeding}
          className="rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 px-8 py-4 text-lg font-semibold text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all disabled:opacity-50"
        >
          {seeding ? 'Setting up...' : '🚀 Initialize Business Workspace'}
        </button>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-20 text-center">
        <div className="animate-pulse text-slate-400 text-lg">Loading your business...</div>
      </main>
    );
  }

  if (!dashboard) return null;

  const health = dashboard.health;

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      {/* Demo Mode Banner */}
      {dashboard.demo_mode && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 flex items-center gap-3">
          <span className="text-amber-600 font-semibold text-sm">⚠️ DEMO MODE</span>
          <span className="text-amber-700 text-sm">This workspace contains synthetic demo data. Data marked with 📋 is demonstration data.</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">{dashboard.company_name}</h1>
          <p className="text-slate-500 mt-1">Executive Command Center — What is happening in your business right now?</p>
        </div>
        <button
          onClick={() => { setShowBriefing(!showBriefing); if (!briefing) fetchBriefing(); }}
          className="rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 px-6 py-3 text-sm font-semibold text-white hover:shadow-lg transition-all"
        >
          {showBriefing ? 'Hide Briefing' : '📋 Executive Briefing'}
        </button>
      </div>

      {/* Natural Language Interface */}
      <div className="mb-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex gap-3">
          <input
            type="text"
            value={askInput}
            onChange={(e) => setAskInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
            placeholder="Ask AgentMason: &quot;What should I focus on today?&quot; · &quot;Find government opportunities&quot; · &quot;Where am I wasting money?&quot;"
            className="flex-1 rounded-lg border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleAsk}
            className="rounded-lg bg-slate-900 px-6 py-3 text-sm font-medium text-white hover:bg-slate-800 transition-colors"
          >
            Ask →
          </button>
        </div>
      </div>

      {/* Executive Briefing (collapsible) */}
      {showBriefing && briefing && (
        <div className="mb-8 rounded-xl border border-blue-200 bg-blue-50/50 p-6 space-y-6">
          <h2 className="text-xl font-bold text-slate-900">📋 Executive Briefing</h2>
          <p className="text-slate-600">{briefing.greeting}</p>

          {briefing.top_priorities.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-800 mb-3">🎯 Top Priorities</h3>
              <div className="space-y-2">
                {briefing.top_priorities.map((p, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${PRIORITY_COLORS[p.priority] || PRIORITY_COLORS.medium}`}>{p.priority}</span>
                      <span className="font-medium text-slate-800 text-sm">{p.title}</span>
                    </div>
                    {p.why && <p className="text-xs text-slate-500 ml-1">Why: {p.why}</p>}
                    {p.action && <p className="text-xs text-blue-600 ml-1 mt-1">→ {p.action}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {briefing.risks.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-800 mb-3">⚠️ Risks</h3>
              {briefing.risks.map((r, i) => (
                <div key={i} className="rounded-lg border border-red-100 bg-red-50/50 p-3 mb-2">
                  <span className="font-medium text-sm text-slate-800">{r.title}</span>
                  <p className="text-xs text-slate-600 mt-1">{r.description}</p>
                </div>
              ))}
            </div>
          )}

          {briefing.opportunities.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-800 mb-3">💡 Opportunities</h3>
              {briefing.opportunities.map((o, i) => (
                <div key={i} className="rounded-lg border border-green-100 bg-green-50/50 p-3 mb-2">
                  <span className="font-medium text-sm text-slate-800">{o.title}</span>
                  <p className="text-xs text-slate-600 mt-1">{o.description}</p>
                  {o.action && <p className="text-xs text-green-700 mt-1">→ {o.action}</p>}
                </div>
              ))}
            </div>
          )}

          {briefing.waiting_for_approval.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-800 mb-3">🔐 Waiting for Your Approval</h3>
              {briefing.waiting_for_approval.map((a, i) => (
                <div key={i} className="rounded-lg border border-purple-100 bg-purple-50/50 p-3 mb-2 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-sm text-slate-800">{a.title}</span>
                    <p className="text-xs text-slate-500">{a.agent_name}</p>
                  </div>
                  <Link href="/approvals" className="text-xs font-medium text-purple-600 hover:text-purple-800">Review →</Link>
                </div>
              ))}
            </div>
          )}

          {briefing.completed_recently.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-800 mb-3">✅ Completed Recently</h3>
              <div className="space-y-1">
                {briefing.completed_recently.slice(0, 5).map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <span className="text-green-500">✓</span>
                    <span className="text-slate-600">{c.action}</span>
                    <span className="text-xs text-slate-400">({c.agent_name})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* KPI Highlights */}
          {briefing.kpi_highlights.length > 0 && (
            <div>
              <h3 className="font-semibold text-slate-800 mb-3">📊 KPI Highlights</h3>
              <div className="grid grid-cols-3 gap-3">
                {briefing.kpi_highlights.slice(0, 6).map((k, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                    <div className="text-xs text-slate-500 mb-1">{k.name} {k.is_demo_data && '📋'}</div>
                    <div className="text-lg font-bold text-slate-900">
                      {k.unit === '$' ? `$${k.value.toLocaleString()}` : `${k.value}${k.unit === '%' ? '%' : ` ${k.unit}`}`}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${k.status === 'on_track' ? 'bg-green-500' : k.status === 'at_risk' ? 'bg-yellow-500' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(k.progress_pct, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400">{k.progress_pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Business Health Cards */}
      <div className="grid grid-cols-5 gap-4 mb-8">
        {[
          { label: 'Revenue', data: health.revenue, icon: '💰' },
          { label: 'Customers', data: health.customers, icon: '👥' },
          { label: 'Pipeline', data: health.pipeline, icon: '📈' },
          { label: 'Expenses', data: health.expenses, icon: '💳' },
          { label: 'Margin', data: health.operating_margin, icon: '📊' },
        ].map(({ label, data, icon }) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-500">{label}</span>
              <span className="text-lg">{icon}</span>
            </div>
            {data ? (
              <>
                <div className="text-2xl font-bold text-slate-900">
                  {data.unit === '$' ? `$${data.value.toLocaleString()}` : `${data.value}${data.unit === '%' ? '%' : ` ${data.unit}`}`}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {data.trend && (
                    <span className={`text-sm ${data.trend === 'up' ? 'text-green-500' : data.trend === 'down' ? 'text-red-500' : 'text-slate-400'}`}>
                      {TREND_ICONS[data.trend] || ''}
                    </span>
                  )}
                  {data.target && (
                    <span className="text-xs text-slate-400">
                      Target: {data.unit === '$' ? `$${data.target.toLocaleString()}` : `${data.target}${data.unit === '%' ? '%' : ''}`}
                    </span>
                  )}
                  {data.is_demo_data && <span className="text-xs">📋</span>}
                </div>
              </>
            ) : (
              <div className="text-sm text-slate-400">No data</div>
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Attention Required */}
        <div className="col-span-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Attention Required</h2>
            <Link href="/inbox" className="text-sm text-blue-600 hover:text-blue-800 font-medium">View All →</Link>
          </div>
          <div className="space-y-3">
            {dashboard.attention_items.length === 0 ? (
              <p className="text-sm text-slate-400">No items need attention right now.</p>
            ) : (
              dashboard.attention_items.map((item) => (
                <div key={item.id} className="flex items-start gap-3 rounded-lg border border-slate-100 p-3 hover:bg-slate-50 transition-colors">
                  <span className="text-lg mt-0.5">{PRIORITY_DOTS[item.priority] || '⚪'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-slate-800">{item.title}</span>
                      {item.is_demo_data && <span className="text-xs">📋</span>}
                      {item.requires_approval && (
                        <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">Needs Approval</span>
                      )}
                    </div>
                    {item.description && (
                      <p className="text-xs text-slate-500 mt-0.5 truncate">{item.description}</p>
                    )}
                    {item.agent_name && (
                      <span className="text-xs text-slate-400 mt-0.5 inline-block">Agent: {item.agent_name}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Summary */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Business Pulse</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">Open Issues</span>
                <span className="text-sm font-semibold text-slate-900">{dashboard.summary.open_attention_items}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">Pending Approvals</span>
                <span className="text-sm font-semibold text-purple-600">{dashboard.summary.pending_approvals}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">Opportunities</span>
                <span className="text-sm font-semibold text-green-600">{dashboard.summary.opportunities}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">Risks</span>
                <span className="text-sm font-semibold text-red-600">{dashboard.summary.risks}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-600">KPIs Tracked</span>
                <span className="text-sm font-semibold text-slate-900">{dashboard.summary.total_kpis}</span>
              </div>
            </div>
          </div>

          {/* Quick Links */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <Link href="/approvals" className="block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-purple-50 hover:border-purple-200 transition-colors">
                🔐 Review Approvals ({dashboard.summary.pending_approvals})
              </Link>
              <Link href="/inbox?category=opportunity" className="block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-green-50 hover:border-green-200 transition-colors">
                💡 View Opportunities ({dashboard.summary.opportunities})
              </Link>
              <Link href="/scenarios" className="block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:border-blue-200 transition-colors">
                🎬 Run Demo Scenarios
              </Link>
              <Link href="/impact" className="block rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-amber-50 hover:border-amber-200 transition-colors">
                📊 AgentMason Impact
              </Link>
            </div>
          </div>

          {/* Recent Agent Activity */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900">Agent Activity</h2>
              <Link href="/activity" className="text-sm text-blue-600 hover:text-blue-800 font-medium">View All →</Link>
            </div>
            <div className="space-y-2">
              {dashboard.recent_activities.map((a) => (
                <div key={a.id} className="flex items-center gap-2 text-sm">
                  <span className="text-green-500">✓</span>
                  <span className="text-slate-600 truncate flex-1">{a.action}</span>
                  {a.is_demo_data && <span className="text-xs">📋</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* KPIs Grid */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Business KPIs</h2>
        <div className="grid grid-cols-5 gap-3">
          {dashboard.kpis.map((kpi) => {
            const progressPct = kpi.target ? Math.min(Math.round(kpi.value / kpi.target * 100), 100) : null;
            const statusColor = progressPct !== null
              ? (progressPct >= 80 ? 'bg-green-500' : progressPct >= 50 ? 'bg-yellow-500' : 'bg-red-500')
              : 'bg-slate-300';
            return (
              <div key={kpi.name} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="text-xs text-slate-500 mb-1 truncate">
                  {kpi.name} {kpi.is_demo_data && '📋'}
                </div>
                <div className={`text-lg font-bold ${CATEGORY_COLORS[kpi.category] || 'text-slate-900'}`}>
                  {kpi.unit === '$' ? `$${kpi.value.toLocaleString()}` : `${kpi.value}${kpi.unit === '%' ? '%' : ` ${kpi.unit}`}`}
                </div>
                {kpi.target && (
                  <div className="mt-2">
                    <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${statusColor}`} style={{ width: `${progressPct}%` }} />
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-xs text-slate-400">{progressPct}% of target</span>
                      {kpi.trend && <span className={`text-xs ${kpi.trend === 'up' ? 'text-green-500' : kpi.trend === 'down' ? 'text-red-500' : 'text-slate-400'}`}>{TREND_ICONS[kpi.trend]}</span>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
