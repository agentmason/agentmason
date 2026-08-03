export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-24">
      <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-10 shadow-2xl shadow-slate-950/50">
        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.3em] text-cyan-400">AgentMason AI Platform</p>
        <h1 className="text-4xl font-semibold sm:text-6xl">Enterprise AI agents, RAG, and governance in one platform.</h1>
        <p className="mt-6 max-w-3xl text-lg text-slate-300">
          The foundation includes a secure API, reusable agent abstractions, prompt and evaluation tooling, and a deployment-ready stack for consulting and regulated environments.
        </p>
        <div className="mt-8 flex gap-4">
          <a className="rounded-lg bg-cyan-600 px-4 py-3 font-medium text-white" href="http://localhost:8000/docs">Open API Docs</a>
          <a className="rounded-lg border border-slate-700 px-4 py-3 font-medium text-slate-200" href="https://github.com">View Repository</a>
        </div>
      </div>
    </main>
  );
}
