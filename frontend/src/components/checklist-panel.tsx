"use client";
import { useCallback, useEffect, useState } from "react";
import { Checklist, completeChecklist, getChecklist } from "@/lib/trust";

type Stage = "move_in" | "move_out";
const LABEL: Record<Stage, string> = { move_in: "Move-in", move_out: "Move-out" };

export function ChecklistPanel({ depositId, refreshKey = 0 }: { depositId: string; refreshKey?: number }) { // guided rooms
  const [c, setC] = useState<Checklist | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => getChecklist(depositId).then(setC, () => setC(null)), [depositId]);
  useEffect(() => { load(); }, [load, refreshKey]);
  if (!c || !c.side) return null;
  const side = c.side;
  const other = side === "tenant" ? "owner" : "tenant";
  const stages = (Object.keys(c.open) as Stage[]).filter((s) => c.open[s] || c.stages[s][side].completedAt);
  if (!stages.length) return null;
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <h3 className="text-base font-medium">Room-by-room checklist</h3>
      <p className="text-xs text-muted">Photograph every room below with the photo uploader. Both sides doing this makes any later dispute quick and fair.</p>
      {stages.map((stage) => {
        const mine = c.stages[stage][side];
        const theirs = c.stages[stage][other];
        const done = new Set(mine.done ?? []);
        return (
          <div key={stage} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium">{LABEL[stage]}: {done.size}/{c.rooms.length} rooms</p>
              <p className="text-xs text-muted">The {other}: {theirs.completedAt ? "finished" : `${theirs.rooms ?? 0} rooms so far`}</p>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-mist" aria-hidden="true">
              <div className="h-full bg-vault" style={{ width: `${(done.size / c.rooms.length) * 100}%` }} />
            </div>
            <ul className="grid gap-1.5 sm:grid-cols-2">
              {c.rooms.map((r) => (
                <li key={r.name} className={`rounded-lg px-3 py-2 text-sm ${done.has(r.name) ? "bg-vault-soft" : "bg-mist"}`}>
                  <span className="font-medium">{done.has(r.name) ? "✓ " : ""}{r.name}</span>
                  <span className="block text-xs text-muted">{r.tip}</span>
                </li>
              ))}
            </ul>
            {mine.completedAt ? (
              <p className="text-sm text-vault">You finished the {LABEL[stage].toLowerCase()} checklist. It&apos;s recorded in the receipt chain.</p>
            ) : c.open[stage] && (
              <button type="button" disabled={done.size < c.rooms.length}
                onClick={() => completeChecklist(depositId, stage).then(setC, (e) => setError(e.message))}
                className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-50">
                {done.size < c.rooms.length ? `${c.rooms.length - done.size} rooms to go` : `Finish ${LABEL[stage].toLowerCase()} checklist`}
              </button>
            )}
          </div>
        );
      })}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}
