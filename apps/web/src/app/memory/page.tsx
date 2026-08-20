'use client';

import { useEffect, useState } from 'react';

interface Memory {
  id: string;
  category: string;
  title: string;
  content: string;
  status: string;
  source: string;
  confidence: number;
  tags: string[] | null;
  created_at: string | null;
  updated_at: string | null;
}

const CATEGORY_LABELS: Record<string, string> = {
  business_fact: 'Business Fact',
  preference: 'Preference',
  goal: 'Goal',
  decision: 'Decision',
  process: 'Process',
  business_rule: 'Business Rule',
};

const CATEGORY_COLORS: Record<string, string> = {
  business_fact: 'bg-blue-50 text-blue-700 border border-blue-200',
  preference: 'bg-purple-50 text-purple-700 border border-purple-200',
  goal: 'bg-green-50 text-green-700 border border-green-200',
  decision: 'bg-amber-50 text-amber-700 border border-amber-200',
  process: 'bg-cyan-50 text-cyan-700 border border-cyan-200',
  business_rule: 'bg-red-50 text-red-700 border border-red-200',
};

export default function MemoryPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Create form state
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newCategory, setNewCategory] = useState('business_fact');

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('q', search);
      if (categoryFilter) params.set('category', categoryFilter);
      const res = await fetch(`/api/memory?${params}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMemories(data.memories);
        setTotal(data.total);
      }
    } catch (e) {
      console.error('Failed to fetch memories', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchMemories();
  }, [search, categoryFilter]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/memory', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          category: newCategory,
          title: newTitle,
          content: newContent,
          source: 'manual',
        }),
      });
      if (res.ok) {
        setShowCreate(false);
        setNewTitle('');
        setNewContent('');
        fetchMemories();
      }
    } catch (e) {
      console.error('Failed to create memory', e);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this memory?')) return;
    try {
      await fetch(`/api/memory/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      fetchMemories();
    } catch (e) {
      console.error('Failed to delete memory', e);
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">Business Memory</h1>
          <p className="mt-1 text-slate-500">
            What AgentMason knows about your business ({total} memories)
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-4 py-2 font-medium text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all"
        >
          + Add Memory
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <input
          type="text"
          placeholder="Search memories..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">All Categories</option>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
          >
            <h2 className="mb-4 text-xl font-semibold text-slate-900">Add Business Memory</h2>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-500">Category</label>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800"
              >
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-500">Title</label>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800"
                placeholder="e.g. Invoice approval threshold"
              />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-500">Content</label>
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                required
                rows={4}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800"
                placeholder="e.g. All invoices above $10,000 require Sarah's approval before payment."
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 px-4 py-2 font-medium text-white hover:shadow-lg hover:shadow-purple-500/25 transition-all"
              >
                Save Memory
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Memory List */}
      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : memories.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-12 text-center">
          <p className="text-lg text-slate-500">No business memories yet.</p>
          <p className="mt-2 text-sm text-slate-400">
            AgentMason will learn about your business over time, or you can add information manually.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="mb-2 flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_COLORS[memory.category] || 'bg-slate-100 text-slate-600'}`}>
                      {CATEGORY_LABELS[memory.category] || memory.category}
                    </span>
                    <span className="text-xs text-slate-400">
                      Confidence: {Math.round(memory.confidence * 100)}%
                    </span>
                  </div>
                  <h3 className="font-medium text-slate-900">{memory.title}</h3>
                  <p className="mt-1 text-sm text-slate-500">{memory.content}</p>
                  {memory.tags && memory.tags.length > 0 && (
                    <div className="mt-2 flex gap-1">
                      {memory.tags.map((tag) => (
                        <span key={tag} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(memory.id)}
                  className="ml-4 text-sm text-slate-400 hover:text-red-500"
                >
                  Delete
                </button>
              </div>
              <div className="mt-3 flex gap-4 text-xs text-slate-400">
                <span>Source: {memory.source.replace('_', ' ')}</span>
                {memory.created_at && (
                  <span>Created: {new Date(memory.created_at).toLocaleDateString()}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
