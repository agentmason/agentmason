'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

interface InboxItem {
  id: string;
  category: string;
  priority: string;
  title: string;
  description: string;
  evidence: string;
  recommended_action: string;
  risk: string;
  why_it_matters: string;
  agent_name: string;
  data_sources: string[];
  status: string;
  requires_approval: boolean;
  is_demo_data: boolean;
  created_at: string;
}

const CATEGORY_TABS = [
  { id: '', label: 'All' },
  { id: 'needs_attention', label: '🔴 Needs Attention' },
  { id: 'needs_approval', label: '🔐 Needs Approval' },
  { id: 'opportunity', label: '💡 Opportunities' },
  { id: 'risk', label: '⚠️ Risks' },
  { id: 'completed', label: '✅ Completed' },
  { id: 'information', label: 'ℹ️ Information' },
];

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-green-100 text-green-800',
};

const CATEGORY_STYLES: Record<string, string> = {
  needs_attention: 'border-l-red-500',
  needs_approval: 'border-l-purple-500',
  opportunity: 'border-l-green-500',
  risk: 'border-l-amber-500',
  completed: 'border-l-slate-300',
  information: 'border-l-blue-500',
};

export default function InboxPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState(searchParams.get('category') || '');
  const [selectedItem, setSelectedItem] = useState<InboxItem | null>(null);

  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  async function fetchInbox() {
    if (!token) { router.push('/login'); return; }
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (category) params.set('category', category);
      const res = await fetch(`/api/business/inbox?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setItems(data.items);
        setTotal(data.total);
      }
    } catch {}
    setLoading(false);
  }

  async function handleAction(itemId: string, action: string) {
    if (!token) return;
    try {
      const res = await fetch(`/api/business/inbox/${itemId}?action=${action}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchInbox();
        if (selectedItem?.id === itemId) setSelectedItem(null);
      }
    } catch {}
  }

  useEffect(() => { fetchInbox(); }, [category]);

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Business Inbox</h1>
          <p className="text-slate-500 text-sm mt-1">AgentMason's important business events and recommendations</p>
        </div>
        <span className="text-sm text-slate-400">{total} items</span>
      </div>

      {/* Category Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200 overflow-x-auto">
        {CATEGORY_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setCategory(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
              category === tab.id
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Item List */}
        <div className="col-span-2 space-y-3">
          {loading ? (
            <div className="text-center py-12 text-slate-400">Loading...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-slate-400">No items in this category.</div>
          ) : (
            items.map((item) => (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`rounded-lg border border-slate-200 border-l-4 ${CATEGORY_STYLES[item.category] || 'border-l-slate-300'} bg-white p-4 cursor-pointer hover:shadow-sm transition-all ${selectedItem?.id === item.id ? 'ring-2 ring-blue-500' : ''}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${PRIORITY_COLORS[item.priority] || ''}`}>
                        {item.priority}
                      </span>
                      <span className="font-medium text-sm text-slate-800">{item.title}</span>
                      {item.is_demo_data && <span className="text-xs">📋</span>}
                      {item.requires_approval && (
                        <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">Approval</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 line-clamp-2">{item.description}</p>
                    <div className="flex items-center gap-3 mt-2">
                      {item.agent_name && <span className="text-xs text-slate-400">🤖 {item.agent_name}</span>}
                      {item.created_at && (
                        <span className="text-xs text-slate-400">
                          {new Date(item.created_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 ml-3">
                    {item.status === 'open' && (
                      <>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAction(item.id, 'resolve'); }}
                          className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded hover:bg-green-100"
                        >
                          Resolve
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAction(item.id, 'dismiss'); }}
                          className="text-xs bg-slate-50 text-slate-500 px-2 py-1 rounded hover:bg-slate-100"
                        >
                          Dismiss
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail Panel */}
        <div className="sticky top-4">
          {selectedItem ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${PRIORITY_COLORS[selectedItem.priority] || ''}`}>
                  {selectedItem.priority}
                </span>
                {selectedItem.is_demo_data && <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">Demo Data</span>}
              </div>

              <h3 className="text-lg font-semibold text-slate-900">{selectedItem.title}</h3>

              {selectedItem.description && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Description</h4>
                  <p className="text-sm text-slate-700">{selectedItem.description}</p>
                </div>
              )}

              {selectedItem.evidence && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Evidence</h4>
                  <p className="text-sm text-slate-700 bg-slate-50 rounded p-3">{selectedItem.evidence}</p>
                </div>
              )}

              {selectedItem.why_it_matters && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Why It Matters</h4>
                  <p className="text-sm text-slate-700">{selectedItem.why_it_matters}</p>
                </div>
              )}

              {selectedItem.recommended_action && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Recommended Action</h4>
                  <p className="text-sm text-blue-700 bg-blue-50 rounded p-3">{selectedItem.recommended_action}</p>
                </div>
              )}

              {selectedItem.risk && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase mb-1">Risk</h4>
                  <p className="text-sm text-amber-700">{selectedItem.risk}</p>
                </div>
              )}

              <div className="border-t border-slate-100 pt-3 space-y-2">
                {selectedItem.agent_name && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-500">Agent</span>
                    <span className="text-slate-700 font-medium">{selectedItem.agent_name}</span>
                  </div>
                )}
                {selectedItem.data_sources && selectedItem.data_sources.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-500">Data Sources</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {selectedItem.data_sources.map((s, i) => (
                        <span key={i} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {selectedItem.status === 'open' && (
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => handleAction(selectedItem.id, 'resolve')}
                    className="flex-1 rounded-lg bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700"
                  >
                    ✓ Resolve
                  </button>
                  <button
                    onClick={() => handleAction(selectedItem.id, 'acknowledge')}
                    className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    Acknowledge
                  </button>
                  <button
                    onClick={() => handleAction(selectedItem.id, 'dismiss')}
                    className="rounded-lg bg-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-300"
                  >
                    Dismiss
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center">
              <p className="text-slate-400 text-sm">Select an item to view details</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
