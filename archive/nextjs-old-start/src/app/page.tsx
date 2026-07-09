"use client";

import { useState } from 'react';

interface AgentApiResponse {
  scenario: {
    targetAccount: { name: string };
    currentCustomer: { name: string };
  };
  networkAgentResult: {
    data: {
      references: string[];
      warmConnections: string[];
      upsellOpportunities: string[];
      socialProof: string[];
    };
  };
  relationshipAgentResult: {
    data: {
      health: {
        level: string;
        score: number;
        summary: string;
        recommendedAction: string;
      };
    };
  };
  conquestAgentResult: {
    data: {
      path: Array<{
        step: number;
        person: string;
        objective: string;
      }>;
    };
  };
  finalActionPlan: {
    executiveSummary: string;
    talkingPoints: string[];
    nextActions: string[];
  };
}

export default function HomePage() {
  const [result, setResult] = useState<AgentApiResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function runAgents() {
    setLoading(true);
    const response = await fetch('/api/run-agents', { method: 'POST' });
    const data = (await response.json()) as AgentApiResponse;
    setResult(data);
    setLoading(false);
  }

  return (
    <main className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <div className="mx-auto max-w-6xl rounded-xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
        <p className="text-sm uppercase tracking-[0.3em] text-cyan-400">Account Conquest Room</p>
        <h1 className="mt-3 text-3xl font-semibold">Demo orchestration flow</h1>
        <p className="mt-4 max-w-2xl text-slate-400">
          Run the agent team to produce a structured action plan for the Qonto and PayFit scenario.
        </p>

        <button
          onClick={runAgents}
          className="mt-6 rounded-lg bg-cyan-500 px-4 py-2 font-medium text-slate-950 transition hover:bg-cyan-400"
        >
          {loading ? 'Running…' : 'Run Agent Team'}
        </button>

        {result && (
          <section className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-6">
              <h2 className="text-xl font-semibold">Executive Summary</h2>
              <p className="mt-3 text-slate-300">{result.finalActionPlan.executiveSummary}</p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-6">
              <h2 className="text-xl font-semibold">Network References</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {result.networkAgentResult.data.references.map((item) => (
                  <li key={item} className="rounded border border-slate-800 bg-slate-900/70 p-2">
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-6">
              <h2 className="text-xl font-semibold">Relationship Risk</h2>
              <p className="mt-3 text-slate-300">{result.relationshipAgentResult.data.health.summary}</p>
              <p className="mt-2 text-sm text-cyan-400">
                Level: {result.relationshipAgentResult.data.health.level} · Score: {result.relationshipAgentResult.data.health.score}
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-6">
              <h2 className="text-xl font-semibold">Conquest Path</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {result.conquestAgentResult.data.path.map((step) => (
                  <li key={step.step} className="rounded border border-slate-800 bg-slate-900/70 p-2">
                    <strong>Step {step.step}:</strong> {step.person} — {step.objective}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-6 lg:col-span-2">
              <h2 className="text-xl font-semibold">Talking Points</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {result.finalActionPlan.talkingPoints.map((item) => (
                  <li key={item} className="rounded border border-slate-800 bg-slate-900/70 p-2">
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-6 lg:col-span-2">
              <h2 className="text-xl font-semibold">Next Actions</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {result.finalActionPlan.nextActions.map((item) => (
                  <li key={item} className="rounded border border-slate-800 bg-slate-900/70 p-2">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
