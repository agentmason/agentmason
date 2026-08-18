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
  business_fact: 'bg-blue-500/20 text-blue-300',
  preference: 'bg-purple-500/20 text-purple-300',
  goal: 'bg-green-500/20 text-green-300',
  decision: 'bg-amber-500/20 text-amber-300',
  process: 'bg-cyan-500/20 text-cyan-300',
  business_rule: 'bg-red-500/20 text-red-300',
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
          <h1 className="text-3xl font-semibold text-white">Business Memory</h1>
          <p className="mt-1 text-slate-400">
            What AgentMason knows about your business ({total} memories)
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-cyan-600 px-4 py-2 font-medium text-white hover:bg-cyan-500"
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
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white focus:border-cyan-500 focus:outline-none"
        >
          <option value="">All Categories</option>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6"
          >
            <h2 className="mb-4 text-xl font-semibold text-white">Add Business Memory</h2>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-400">Category</label>
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white"
              >
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-400">Title</label>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white"
                placeholder="e.g. Invoice approval threshold"
              />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-400">Content</label>
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                required
                rows={4}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white"
                placeholder="e.g. All invoices above $10,000 require Sarah's approval before payment."
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-cyan-600 px-4 py-2 font-medium text-white hover:bg-cyan-500"
              >
                Save Memory
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Memory List */}
      {loading ? (
        <p className="text-slate-400">Loading...</p>
      ) : memories.length === 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-12 text-center">
          <p className="text-lg text-slate-400">No business memories yet.</p>
          <p className="mt-2 text-sm text-slate-500">
            AgentMason will learn about your business over time, or you can add information manually.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="rounded-xl border border-slate-800 bg-slate-900/70 p-5"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="mb-2 flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_COLORS[memory.category] || 'bg-slate-700 text-slate-300'}`}>
                      {CATEGORY_LABELS[memory.category] || memory.category}
                    </span>
                    <span className="text-xs text-slate-500">
                      Confidence: {Math.round(memory.confidence * 100)}%
                    </span>
                  </div>
                  <h3 className="font-medium text-white">{memory.title}</h3>
                  <p className="mt-1 text-sm text-slate-400">{memory.content}</p>
                  {memory.tags && memory.tags.length > 0 && (
                    <div className="mt-2 flex gap-1">
                      {memory.tags.map((tag) => (
                        <span key={tag} className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-500">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(memory.id)}
                  className="ml-4 text-sm text-slate-500 hover:text-red-400"
                >
                  Delete
                </button>
              </div>
              <div className="mt-3 flex gap-4 text-xs text-slate-600">
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
