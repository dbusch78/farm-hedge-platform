"use client";

import { useEffect, useState, useTransition } from "react";
import type { AgentRun } from "@/lib/types";
import { getAgentRuns, triggerAgentRun } from "@/lib/api";

const AGENTS = [
  { name: "positioning_advisor", label: "Positioning Advisor", icon: "🤖" },
  { name: "usda_skeptic",        label: "USDA Skeptic",        icon: "📊" },
  { name: "sa_monitor",          label: "SA Monitor",          icon: "🌎" },
  { name: "weather_analyst",     label: "Weather Analyst",     icon: "🌤️" },
  { name: "news_filter",         label: "News Filter",         icon: "📰" },
];

function fmt(n: number) {
  return n.toFixed(0);
}

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 1) return "< 1h ago";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function AnnotateForm({
  run,
  onSaved,
}: {
  run: AgentRun;
  onSaved: () => void;
}) {
  const [outcome, setOutcome] = useState(run.actual_outcome ?? "");
  const [notes, setNotes] = useState(run.outcome_notes ?? "");
  const [rating, setRating] = useState<number | "">(run.operator_rating ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await fetch(`/api/agents/runs/${run.id}/annotate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actual_outcome: outcome || null,
          outcome_notes: notes || null,
          operator_rating: rating !== "" ? Number(rating) : null,
        }),
      });
      setSaved(true);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-[#2a3044] space-y-2 text-xs">
      <p className="text-[#7b8aab] font-semibold uppercase tracking-wide">Annotation</p>
      <input
        className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1 text-[#e8edf5] placeholder-[#4a5568]"
        placeholder="Actual outcome (e.g. ZC rallied 20¢ after WASDE)"
        value={outcome}
        onChange={(e) => setOutcome(e.target.value)}
      />
      <input
        className="w-full bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1 text-[#e8edf5] placeholder-[#4a5568]"
        placeholder="Notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      <div className="flex items-center gap-3">
        <select
          className="bg-[#0f1117] border border-[#2a3044] rounded px-2 py-1 text-[#e8edf5]"
          value={rating}
          onChange={(e) => setRating(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">Rating</option>
          {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v} ★</option>)}
        </select>
        <button
          onClick={save}
          disabled={saving}
          className="bg-[#3b82f620] text-[#3b82f6] border border-[#3b82f640] rounded px-3 py-1 hover:bg-[#3b82f640] disabled:opacity-40"
        >
          {saved ? "Saved ✓" : saving ? "Saving…" : "Save annotation"}
        </button>
      </div>
    </div>
  );
}

function RunCard({ run }: { run: AgentRun }) {
  const [expanded, setExpanded] = useState(false);
  const output = run.output;
  const confidence = output?.confidence as number | undefined;

  return (
    <div className="bg-[#141920] rounded border border-[#2a3044] p-3 text-xs space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-semibold text-[#e8edf5]">
            {AGENTS.find((a) => a.name === run.agent)?.icon}{" "}
            {AGENTS.find((a) => a.name === run.agent)?.label ?? run.agent}
          </span>
          <span className="ml-2 text-[#4a5568]">{run.prompt_version}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0 text-[#7b8aab]">
          {confidence !== undefined && (
            <span className={confidence >= 0.7 ? "text-[#22c55e]" : confidence >= 0.5 ? "text-[#f59e0b]" : "text-[#ef4444]"}>
              {fmt(confidence * 100)}%
            </span>
          )}
          <span>${(run.cost_usd * 100).toFixed(2)}¢</span>
          <span>{timeAgo(run.run_timestamp)}</span>
        </div>
      </div>

      {output?.summary && (
        <p className="text-[#9aa5be] leading-relaxed line-clamp-3">
          {output.summary as string}
        </p>
      )}

      {run.actual_outcome && (
        <div className="text-[10px] bg-[#22c55e10] border border-[#22c55e30] rounded px-2 py-1 text-[#22c55e]">
          Outcome: {run.actual_outcome}
          {run.operator_rating != null && ` — ${run.operator_rating}★`}
        </div>
      )}

      <button
        onClick={() => setExpanded((v) => !v)}
        className="text-[#3b82f6] hover:underline"
      >
        {expanded ? "Hide details" : "Show details / annotate"}
      </button>

      {expanded && (
        <div className="space-y-3">
          <pre className="bg-[#0f1117] rounded p-2 text-[10px] text-[#7b8aab] overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(output, null, 2)}
          </pre>
          <AnnotateForm run={run} onSaved={() => {}} />
        </div>
      )}
    </div>
  );
}

export default function AgentsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function load() {
    setLoading(true);
    try {
      const agent = filter === "all" ? undefined : filter;
      const data = await getAgentRuns(agent, 50);
      setRuns(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [filter]);

  async function triggerAgent(agentName: string) {
    setTriggering(agentName);
    try {
      await triggerAgentRun(agentName);
      // Wait a moment then reload — background task takes a few seconds
      setTimeout(() => {
        startTransition(() => { load(); });
        setTriggering(null);
      }, 5000);
    } catch (e) {
      console.error(e);
      setTriggering(null);
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[#e8edf5]">AI Agents</h1>
        <a href="/" className="text-xs text-[#3b82f6] hover:underline">← Dashboard</a>
      </div>

      {/* Trigger buttons */}
      <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] p-4 space-y-3">
        <p className="text-xs text-[#7b8aab] font-semibold uppercase tracking-wide">
          Manual Triggers
        </p>
        <div className="flex flex-wrap gap-2">
          {AGENTS.map((a) => (
            <button
              key={a.name}
              onClick={() => triggerAgent(a.name)}
              disabled={triggering !== null}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                triggering === a.name
                  ? "bg-[#f59e0b20] border-[#f59e0b60] text-[#f59e0b] cursor-wait"
                  : "bg-[#1e2535] border-[#2a3044] text-[#9aa5be] hover:text-[#e8edf5] hover:border-[#3b82f6] disabled:opacity-40"
              }`}
            >
              {triggering === a.name ? "Running…" : `${a.icon} ${a.label}`}
            </button>
          ))}
        </div>
        {triggering && (
          <p className="text-[10px] text-[#7b8aab]">
            Agent running in background. Results will appear in ~10 seconds.
          </p>
        )}
      </div>

      {/* Filter */}
      <div className="flex gap-2 text-xs flex-wrap">
        <button
          onClick={() => setFilter("all")}
          className={`px-3 py-1 rounded ${filter === "all" ? "bg-[#3b82f620] text-[#3b82f6] border border-[#3b82f640]" : "text-[#7b8aab] hover:text-[#e8edf5]"}`}
        >
          All agents
        </button>
        {AGENTS.map((a) => (
          <button
            key={a.name}
            onClick={() => setFilter(a.name)}
            className={`px-3 py-1 rounded ${filter === a.name ? "bg-[#3b82f620] text-[#3b82f6] border border-[#3b82f640]" : "text-[#7b8aab] hover:text-[#e8edf5]"}`}
          >
            {a.icon} {a.label}
          </button>
        ))}
      </div>

      {/* Run list */}
      {loading ? (
        <div className="text-sm text-[#4a5568] italic">Loading…</div>
      ) : runs.length === 0 ? (
        <div className="text-sm text-[#4a5568] italic">
          No runs yet. Trigger an agent above, or wait for the scheduled run.
        </div>
      ) : (
        <div className="space-y-3">
          {runs.map((run) => (
            <RunCard key={run.id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}
