'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface ApprovalItem {
  id: string;
  source: string;
  title: string;
  description: string;
  reason: string;
  risk: string;
  agent_name: string;
  data_sources: string[];
  recommended_action: string;
  evidence: string;
  is_demo_data: boolean;
  created_at: string;
}

export default function ApprovalsPage() {
  const router = useRouter();
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  async function fetchApprovals() {
    if (!token) { router.push('/login'); return; }
    try {
      const res = await fetch('/api/business/approvals', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setApprovals(data.approvals);
      }
    } catch {}
    setLoading(false);
  }

  async function decide(itemId: string, decision: string, note?: string) {
    if (!token) return;
    setDecidingId(itemId);
    try {
      const res = await fetch(`/api/business/approvals/${itemId}/decide`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, note }),
      });
      if (res.ok) fetchApprovals();
    } catch {}
    setDecidingId(null);
  }

  useEffect(() => { fetchApprovals(); }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">🔐 Needs My Approval</h1>
        <p className="text-slate-500 text-sm mt-1">Review and decide on actions recommended by AgentMason</p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading approvals...</div>
      ) : approvals.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-4">✅</div>
          <h2 className="text-lg font-semibold text-slate-700">All caught up!</h2>
          <p className="text-slate-400 text-sm mt-1">No actions require your approval right now.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map((item) => (
            <div key={item.id} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-lg font-semibold text-slate-900">{item.title}</h3>
                    {item.is_demo_data && (
                      <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">Demo Data</span>
                    )}
                  </div>
                  {item.description && <p className="text-sm text-slate-600">{item.description}</p>}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-4">
                {item.reason && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Why It Matters</h4>
                    <p className="text-sm text-slate-700">{item.reason}</p>
                  </div>
                )}
                {item.risk && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Risk</h4>
                    <p className="text-sm text-amber-700">{item.risk}</p>
                  </div>
                )}
              </div>

              {item.evidence && (
                <div className="mb-4">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Evidence</h4>
                  <p className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{item.evidence}</p>
                </div>
              )}

              {item.recommended_action && (
                <div className="mb-4">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Recommended Action</h4>
                  <p className="text-sm text-blue-700 bg-blue-50 rounded-lg p-3">{item.recommended_action}</p>
                </div>
              )}

              <div className="flex items-center justify-between border-t border-slate-100 pt-4">
                <div className="flex items-center gap-4 text-sm text-slate-400">
                  {item.agent_name && <span>🤖 {item.agent_name}</span>}
                  {item.data_sources && item.data_sources.length > 0 && (
                    <span>📂 {item.data_sources.join(', ')}</span>
                  )}
                  {item.source && <span className="bg-slate-100 text-slate-500 px-2 py-0.5 rounded text-xs">Source: {item.source}</span>}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => decide(item.id, 'approve')}
                    disabled={decidingId === item.id}
                    className="rounded-lg bg-green-600 px-5 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => decide(item.id, 'edit')}
                    disabled={decidingId === item.id}
                    className="rounded-lg bg-blue-100 px-5 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-200 disabled:opacity-50 transition-colors"
                  >
                    ✏️ Edit
                  </button>
                  <button
                    onClick={() => decide(item.id, 'reject')}
                    disabled={decidingId === item.id}
                    className="rounded-lg bg-red-100 px-5 py-2 text-sm font-semibold text-red-700 hover:bg-red-200 disabled:opacity-50 transition-colors"
                  >
                    ✕ Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
