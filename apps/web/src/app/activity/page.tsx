'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface ActivityItem {
  id: string;
  agent_name: string;
  action: string;
  detail: string;
  result: string;
  workflow_id: string | null;
  data_sources: string[];
  is_demo_data: boolean;
  created_at: string;
}

const AGENT_ICONS: Record<string, string> = {
  'Executive Agent': '👔',
  'Sales Agent': '🤝',
  'Marketing Agent': '📣',
  'Finance Agent': '💰',
  'Operations Agent': '⚙️',
  'Product Agent': '📦',
  'Engineering Agent': '🛠️',
  'Government Contracts Agent': '🏛️',
  'Customer Success Agent': '🎯',
  'Orchestrator': '🎭',
};

const AGENT_COLORS: Record<string, string> = {
  'Executive Agent': 'border-l-slate-500',
  'Sales Agent': 'border-l-blue-500',
  'Marketing Agent': 'border-l-pink-500',
  'Finance Agent': 'border-l-emerald-500',
  'Operations Agent': 'border-l-cyan-500',
  'Product Agent': 'border-l-purple-500',
  'Engineering Agent': 'border-l-indigo-500',
  'Government Contracts Agent': 'border-l-rose-500',
  'Customer Success Agent': 'border-l-amber-500',
  'Orchestrator': 'border-l-violet-500',
};

export default function ActivityPage() {
  const router = useRouter();
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [agentFilter, setAgentFilter] = useState('');
  const [selectedActivity, setSelectedActivity] = useState<ActivityItem | null>(null);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  async function fetchActivities() {
    if (!token) { router.push('/login'); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (agentFilter) params.set('agent_name', agentFilter);
      params.set('limit', '100');
      const res = await fetch(`/api/business/activities?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setActivities(data.activities);
        setTotal(data.total);
      }
    } catch {}
    setLoading(false);
  }

  useEffect(() => { fetchActivities(); }, [agentFilter]);

  const uniqueAgents = [...new Set(activities.map(a => a.agent_name))].sort();

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">What AgentMason Did</h1>
          <p className="text-slate-500 text-sm mt-1">Complete history of agent actions and results</p>
        </div>
        <span className="text-sm text-slate-400">{total} actions recorded</span>
      </div>

      {/* Agent Filter */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <button
          onClick={() => setAgentFilter('')}
          className={`px-3 py-1.5 text-sm rounded-full transition-colors ${!agentFilter ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
        >
          All Agents
        </button>
        {uniqueAgents.map((agent) => (
          <button
            key={agent}
            onClick={() => setAgentFilter(agent)}
            className={`px-3 py-1.5 text-sm rounded-full transition-colors ${agentFilter === agent ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
          >
            {AGENT_ICONS[agent] || '🤖'} {agent}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Activity List */}
        <div className="col-span-2 space-y-2">
          {loading ? (
            <div className="text-center py-12 text-slate-400">Loading activities...</div>
          ) : activities.length === 0 ? (
            <div className="text-center py-12 text-slate-400">No agent activities recorded yet.</div>
          ) : (
            activities.map((act) => (
              <div
                key={act.id}
                onClick={() => setSelectedActivity(act)}
                className={`rounded-lg border border-slate-200 border-l-4 ${AGENT_COLORS[act.agent_name] || 'border-l-slate-300'} bg-white p-4 cursor-pointer hover:shadow-sm transition-all ${selectedActivity?.id === act.id ? 'ring-2 ring-blue-500' : ''}`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-xl mt-0.5">{AGENT_ICONS[act.agent_name] || '🤖'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-green-500 text-sm">✓</span>
                      <span className="font-medium text-sm text-slate-800">{act.action}</span>
                      {act.is_demo_data && <span className="text-xs">📋</span>}
                    </div>
                    {act.result && (
                      <p className="text-xs text-slate-500 truncate">{act.result}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-slate-400">{act.agent_name}</span>
                      {act.created_at && (
                        <span className="text-xs text-slate-400">
                          {new Date(act.created_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail Panel */}
        <div className="sticky top-4">
          {selectedActivity ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{AGENT_ICONS[selectedActivity.agent_name] || '🤖'}</span>
                <div>
                  <h3 className="font-semibold text-slate-900">{selectedActivity.agent_name}</h3>
                  {selectedActivity.is_demo_data && (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">Demo Data</span>
                  )}
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Action</h4>
                <p className="text-sm text-slate-800 font-medium">{selectedActivity.action}</p>
              </div>

              {selectedActivity.detail && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Detail</h4>
                  <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{selectedActivity.detail}</p>
                </div>
              )}

              {selectedActivity.result && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Result</h4>
                  <p className="text-sm text-green-700 bg-green-50 rounded-lg p-3">{selectedActivity.result}</p>
                </div>
              )}

              {selectedActivity.data_sources && selectedActivity.data_sources.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Data Sources</h4>
                  <div className="flex flex-wrap gap-1">
                    {selectedActivity.data_sources.map((s, i) => (
                      <span key={i} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {selectedActivity.created_at && (
                <div className="border-t border-slate-100 pt-3">
                  <span className="text-xs text-slate-400">
                    {new Date(selectedActivity.created_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
              <p className="text-slate-400 text-sm">Select an activity to view details</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
