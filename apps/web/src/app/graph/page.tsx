'use client';

import { useEffect, useState, useCallback } from 'react';

interface Entity {
  id: string;
  entity_type: string;
  name: string;
  description: string | null;
  properties: Record<string, unknown> | null;
}

interface Relationship {
  relationship_id: string;
  relationship_type: string;
  direction: string;
  connected_entity: { id: string; name: string; entity_type: string } | null;
  strength: number;
}

const TYPE_COLORS: Record<string, string> = {
  company: '#06b6d4',
  person: '#8b5cf6',
  employee: '#8b5cf6',
  customer: '#10b981',
  vendor: '#f59e0b',
  product: '#3b82f6',
  service: '#3b82f6',
  department: '#ec4899',
  location: '#14b8a6',
  project: '#6366f1',
  contract: '#f97316',
  order: '#84cc16',
  invoice: '#eab308',
  document: '#64748b',
  process: '#06b6d4',
  goal: '#22c55e',
  decision: '#f59e0b',
  business_rule: '#ef4444',
};

export default function GraphPage() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [showCreate, setShowCreate] = useState(false);

  // Create form
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('company');
  const [newDescription, setNewDescription] = useState('');

  const fetchEntities = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('q', search);
      if (typeFilter) params.set('entity_type', typeFilter);
      const res = await fetch(`/api/graph/entities?${params}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEntities(data.entities);
        setTotal(data.total);
      }
    } catch (e) {
      console.error('Failed to fetch entities', e);
    }
    setLoading(false);
  };

  const fetchRelationships = async (entityId: string) => {
    try {
      const res = await fetch(`/api/graph/entities/${entityId}/relationships`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRelationships(data.relationships);
      }
    } catch (e) {
      console.error('Failed to fetch relationships', e);
    }
  };

  useEffect(() => {
    fetchEntities();
  }, [search, typeFilter]);

  const handleSelectEntity = (entity: Entity) => {
    setSelectedEntity(entity);
    fetchRelationships(entity.id);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/graph/entities', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          entity_type: newType,
          name: newName,
          description: newDescription || null,
        }),
      });
      if (res.ok) {
        setShowCreate(false);
        setNewName('');
        setNewDescription('');
        fetchEntities();
      }
    } catch (e) {
      console.error('Failed to create entity', e);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this entity and all its relationships?')) return;
    try {
      await fetch(`/api/graph/entities/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (selectedEntity?.id === id) {
        setSelectedEntity(null);
        setRelationships([]);
      }
      fetchEntities();
    } catch (e) {
      console.error('Failed to delete entity', e);
    }
  };

  const entityTypes = Object.keys(TYPE_COLORS);

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-white">Business Graph</h1>
          <p className="mt-1 text-slate-400">
            Entities and relationships in your business ({total} entities)
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-cyan-600 px-4 py-2 font-medium text-white hover:bg-cyan-500"
        >
          + Add Entity
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <input
          type="text"
          placeholder="Search entities..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-white focus:border-cyan-500 focus:outline-none"
        >
          <option value="">All Types</option>
          {entityTypes.map((t) => (
            <option key={t} value={t}>{t.replace('_', ' ')}</option>
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
            <h2 className="mb-4 text-xl font-semibold text-white">Add Entity</h2>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-400">Type</label>
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white"
              >
                {entityTypes.map((t) => (
                  <option key={t} value={t}>{t.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-400">Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white"
                placeholder="e.g. Acme Corp"
              />
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-sm text-slate-400">Description</label>
              <textarea
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white"
                placeholder="Optional description"
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
                Create Entity
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Main Layout: List + Detail */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Entity List */}
        <div className="lg:col-span-2">
          {loading ? (
            <p className="text-slate-400">Loading...</p>
          ) : entities.length === 0 ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-12 text-center">
              <p className="text-lg text-slate-400">No business entities yet.</p>
              <p className="mt-2 text-sm text-slate-500">
                Add entities to build your business graph.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {entities.map((entity) => (
                <div
                  key={entity.id}
                  onClick={() => handleSelectEntity(entity)}
                  className={`cursor-pointer rounded-xl border p-4 transition ${
                    selectedEntity?.id === entity.id
                      ? 'border-cyan-500 bg-slate-800/80'
                      : 'border-slate-800 bg-slate-900/70 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: TYPE_COLORS[entity.entity_type] || '#64748b' }}
                      />
                      <div>
                        <h3 className="font-medium text-white">{entity.name}</h3>
                        <span className="text-xs text-slate-500">
                          {entity.entity_type.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(entity.id); }}
                      className="text-xs text-slate-600 hover:text-red-400"
                    >
                      Delete
                    </button>
                  </div>
                  {entity.description && (
                    <p className="mt-2 text-sm text-slate-400">{entity.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <div className="lg:col-span-1">
          {selectedEntity ? (
            <div className="sticky top-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <div className="mb-4 flex items-center gap-2">
                <div
                  className="h-4 w-4 rounded-full"
                  style={{ backgroundColor: TYPE_COLORS[selectedEntity.entity_type] || '#64748b' }}
                />
                <h2 className="text-lg font-semibold text-white">{selectedEntity.name}</h2>
              </div>
              <p className="mb-2 text-xs text-slate-500 uppercase">
                {selectedEntity.entity_type.replace('_', ' ')}
              </p>
              {selectedEntity.description && (
                <p className="mb-4 text-sm text-slate-400">{selectedEntity.description}</p>
              )}

              <h3 className="mb-2 mt-4 text-sm font-medium text-slate-300">
                Relationships ({relationships.length})
              </h3>
              {relationships.length === 0 ? (
                <p className="text-xs text-slate-500">No relationships yet.</p>
              ) : (
                <div className="space-y-2">
                  {relationships.map((rel) => (
                    <div
                      key={rel.relationship_id}
                      className="rounded-lg border border-slate-800 bg-slate-800/50 p-3"
                    >
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-slate-500">
                          {rel.direction === 'outgoing' ? '→' : '←'}
                        </span>
                        <span className="font-medium text-cyan-400">
                          {rel.relationship_type.replace('_', ' ')}
                        </span>
                      </div>
                      {rel.connected_entity && (
                        <p
                          className="mt-1 cursor-pointer text-sm text-white hover:text-cyan-300"
                          onClick={() => {
                            const found = entities.find(e => e.id === rel.connected_entity!.id);
                            if (found) handleSelectEntity(found);
                          }}
                        >
                          {rel.connected_entity.name}
                          <span className="ml-1 text-xs text-slate-500">
                            ({rel.connected_entity.entity_type.replace('_', ' ')})
                          </span>
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8 text-center">
              <p className="text-sm text-slate-500">
                Select an entity to see its relationships
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
