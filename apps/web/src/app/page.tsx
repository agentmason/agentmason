export default function HomePage() {
  return (
    <main className="relative overflow-hidden">
      {/* Hero Section */}
      <div className="mx-auto max-w-7xl px-6 pb-24 pt-20">
        {/* Badge */}
        <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold uppercase tracking-wider text-blue-600 shadow-sm">
          <span>☆</span> AI Agents That Deliver
        </div>

        {/* Headline */}
        <h1 className="max-w-4xl text-5xl font-bold leading-tight tracking-tight text-slate-900 sm:text-6xl lg:text-7xl">
          AI agents that{' '}
          <span className="bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">design, build,</span>{' '}
          and orchestrate delivery
        </h1>

        {/* Subtitle */}
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-500">
          AgentMason.ai helps organizations identify operational problems, design the right solutions, build with precision, implement end-to-end, and support outcomes that scale.
        </p>

        {/* CTA Buttons */}
        <div className="mt-10 flex gap-4">
          <a
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-purple-500/25 hover:shadow-xl hover:shadow-purple-500/30 transition-all"
          >
            Open Dashboard <span className="text-lg">↗</span>
          </a>
          <a
            href="/scenarios"
            className="inline-flex items-center rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            🎬 Run Demo Scenarios
          </a>
        </div>
      </div>

      {/* Feature Cards */}
      <div className="mx-auto max-w-7xl px-6 pb-24">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <a href="/workflows" className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-blue-200 transition-all">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-2xl">⚡</div>
            <h3 className="font-semibold text-slate-900">Workflows</h3>
            <p className="mt-2 text-sm text-slate-500">Build, execute, and monitor autonomous business workflows with AI planning.</p>
          </a>
          <a href="/memory" className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-purple-200 transition-all">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-purple-50 text-2xl">🧠</div>
            <h3 className="font-semibold text-slate-900">Memory</h3>
            <p className="mt-2 text-sm text-slate-500">Business memory that helps agents learn and retain context across interactions.</p>
          </a>
          <a href="/graph" className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-2xl">🔗</div>
            <h3 className="font-semibold text-slate-900">Knowledge Graph</h3>
            <p className="mt-2 text-sm text-slate-500">Map entities and relationships to build a connected business graph.</p>
          </a>
          <a href="http://localhost:8000/docs" className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-green-200 transition-all">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-green-50 text-2xl">📡</div>
            <h3 className="font-semibold text-slate-900">API</h3>
            <p className="mt-2 text-sm text-slate-500">Secure REST API with RAG, agents, evaluation, and governance built in.</p>
          </a>
        </div>
      </div>

      {/* Background gradient */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-96 bg-gradient-to-t from-purple-50/80 via-blue-50/40 to-transparent" />
    </main>
  );
}
