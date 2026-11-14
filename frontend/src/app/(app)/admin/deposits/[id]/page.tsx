"use client";
import Link from "next/link";
import { FormEvent, use, useCallback, useEffect, useState } from "react";
import { VerifiedBadge } from "@/components/deposit-card";
import { NoteList } from "@/components/dispute-notes";
import { addNote, adminSettle, getWorkspace, PhotoRef, STATUS_LABEL, Workspace } from "@/lib/deposits";
import { photoBlobUrl } from "@/lib/condition";
import { formatINR } from "@/lib/format";

const when = (iso: string | null) => iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : "";

function Photo({ depositId, p, label }: { depositId: string; p: PhotoRef; label: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let live = true;
    photoBlobUrl(depositId, p.id).then((u) => { url = u; if (live) setSrc(u); else URL.revokeObjectURL(u); }, () => {});
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [depositId, p.id]);
  return (
    <figure className="flex flex-col gap-1">
      <a href={src ?? undefined} target="_blank" rel="noopener noreferrer" className="block aspect-[4/3] overflow-hidden rounded-lg border border-line bg-mist">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {src ? <img src={src} alt={label} className="h-full w-full object-cover" /> : <span className="flex h-full items-center justify-center text-xs text-muted">Loading...</span>}
      </a>
      <figcaption className="text-xs text-muted">{when(p.at)}{p.note ? ` · ${p.note}` : ""}</figcaption>
    </figure>
  );
}

function RoomRow({ depositId, room, cell }: { depositId: string; room: string; cell: Workspace["photos"][string] }) {
  const col = (stage: "move_in" | "move_out") => {
    const list = [...cell[stage].tenant.map((p) => ({ p, side: "tenant" })), ...cell[stage].owner.map((p) => ({ p, side: "owner" }))];
    return list.length ? (
      <div className="grid grid-cols-2 gap-2">
        {list.map(({ p, side }) => (
          <div key={p.id} className="flex flex-col gap-0.5">
            <span className="text-xs font-medium capitalize">{side}</span>
            <Photo depositId={depositId} p={p} label={`${room}, ${stage === "move_in" ? "move-in" : "move-out"}, by the ${side}`} />
          </div>
        ))}
      </div>
    ) : <p className="text-xs text-muted">No photos</p>;
  };
  return (
    <div className="grid gap-3 border-t border-line pt-3 md:grid-cols-[140px_minmax(0,1fr)_minmax(0,1fr)]">
      <p className="text-sm font-medium">{room}</p>
      <div><p className="mb-1 text-xs text-muted md:hidden">Move-in</p>{col("move_in")}</div>
      <div><p className="mb-1 text-xs text-muted md:hidden">Move-out</p>{col("move_out")}</div>
    </div>
  );
}

export default function DisputeWorkspacePage({ params }: { params: Promise<{ id: string }> }) { // dispute workspace
  const { id } = use(params);
  const [ws, setWs] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deducted, setDeducted] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => getWorkspace(id).then((w) => {
    setWs(w);
    setDeducted((v) => v || String(w.ownerAsked ?? 0));
  }, (e) => setError(e.message)), [id]);
  useEffect(() => { load(); }, [load]);
  if (error && !ws) return <p role="alert" className="text-sm text-claim">{error}</p>;
  if (!ws) return <p className="text-sm text-muted" role="status">Loading...</p>;
  const d = ws.deposit;
  async function decide(e: FormEvent) {
    e.preventDefault();
    if (!confirm(`Settle ${d.id}: keep ${formatINR(Number(deducted) || 0)} for the owner and refund ${formatINR(d.amount - (Number(deducted) || 0))}? This is final.`)) return;
    setBusy(true);
    setError(null);
    try {
      await adminSettle(d.id, Number(deducted) || 0, reason);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not settle.");
    } finally {
      setBusy(false);
    }
  }
  async function post(e: FormEvent) {
    e.preventDefault();
    try {
      await addNote(d.id, note);
      setNote("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the note.");
    }
  }
  const rooms = Object.entries(ws.photos);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/admin/deposits" className="text-sm text-vault hover:underline">← All deposits</Link>
          <h1 className="text-2xl sm:text-3xl">Deposit {d.id}</h1>
          <p className="text-muted">{d.listing.title}, {d.listing.area}</p>
        </div>
        <span className="rounded-full bg-mist px-3 py-1 text-sm font-medium">{STATUS_LABEL[d.status]}</span>
      </div>
      <section className="grid gap-4 rounded-2xl border border-line bg-surface p-5 sm:grid-cols-4">
        <div><p className="text-xs text-muted">Deposit</p><p className="text-lg font-semibold tabular">{formatINR(d.amount)}</p></div>
        <div><p className="text-xs text-muted">Owner asks to keep</p><p className="text-lg font-semibold tabular text-claim">{formatINR(ws.ownerAsked ?? 0)}</p></div>
        <div className="sm:col-span-2"><p className="text-xs text-muted">Owner&apos;s reason</p><p className="text-sm">{d.reason || "No deduction proposed"}</p></div>
        {[["Tenant", ws.tenant], ["Owner", ws.owner]].map(([label, p]) => p && typeof p === "object" && (
          <div key={label as string} className="sm:col-span-2 text-sm">
            <p className="text-xs text-muted">{label as string}</p>
            <p className="font-medium">{p.name} {p.verified ? <span className="text-xs text-vault">ID verified</span> : null}</p>
            <p className="text-muted">{p.email}{p.phone ? ` · ${p.phone}` : ""}</p>
          </div>
        ))}
        <div className="sm:col-span-4"><VerifiedBadge d={d} /></div>
      </section>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
            <h2 className="text-lg">Room by room</h2>
            <div className="hidden gap-3 text-xs font-medium text-muted md:grid md:grid-cols-[140px_minmax(0,1fr)_minmax(0,1fr)]">
              <span>Room</span><span>Move-in</span><span>Move-out</span>
            </div>
            {rooms.length ? rooms.map(([room, cell]) => <RoomRow key={room} depositId={d.id} room={room} cell={cell} />)
              : <p className="text-sm text-muted">Neither side uploaded condition photos.</p>}
          </section>
          <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
            <h2 className="text-lg">Statements</h2>
            <NoteList notes={ws.notes} />
            {ws.canDecide && (
              <form onSubmit={post} className="flex flex-col gap-2">
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000} placeholder="Ask either side a question; both are emailed."
                  className="rounded-lg border border-line px-3 py-2 text-sm" />
                <button type="submit" disabled={note.trim().length < 5} className="w-fit rounded-lg border border-line px-3 py-1.5 text-sm hover:border-ink/40 disabled:opacity-50">Post as reviewer</button>
              </form>
            )}
          </section>
          <section className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-5">
            <h2 className="text-lg">Chat between them</h2>
            {ws.chat.length ? (
              <ul className="flex max-h-96 flex-col gap-1.5 overflow-y-auto text-sm">
                {ws.chat.map((m, i) => (
                  <li key={i} className={`max-w-[85%] rounded-lg px-3 py-1.5 ${m.from === "tenant" ? "self-start bg-mist" : "self-end bg-vault-soft"}`}>
                    <span className="block text-xs text-muted capitalize">{m.from} · {when(m.at)}</span>{m.text}
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted">No messages.</p>}
          </section>
        </div>
        <aside className="flex flex-col gap-6">
          {ws.canDecide ? (
            <form onSubmit={decide} className="flex flex-col gap-3 rounded-2xl border-2 border-vault/40 bg-surface p-5">
              <h2 className="text-lg">Decision</h2>
              <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Owner keeps (₹)</span>
                <input inputMode="numeric" value={deducted} onChange={(e) => setDeducted(e.target.value.replace(/\D/g, ""))} className="rounded-lg border border-line px-3 py-2" /></label>
              <label className="flex flex-col gap-1 text-sm"><span className="text-xs text-muted">Reason (both sides see it)</span>
                <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} className="rounded-lg border border-line px-3 py-2" /></label>
              <p className="text-xs text-muted">Refund to tenant: {formatINR(Math.max(0, d.amount - (Number(deducted) || 0)))}</p>
              <button type="submit" disabled={busy} className="rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">Settle deposit</button>
              {error && <p role="alert" className="text-sm text-claim">{error}</p>}
            </form>
          ) : (
            <p className="rounded-2xl border border-line bg-surface p-5 text-sm">Settled: {formatINR(d.refunded ?? 0)} refunded, {formatINR(d.deducted ?? 0)} kept.</p>
          )}
          <section className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-5">
            <h2 className="text-lg">Timeline</h2>
            <ol className="flex flex-col gap-2 border-l border-line pl-4 text-sm">
              {ws.timeline.map((e, i) => (
                <li key={i}><p className="text-xs text-muted">{when(e.at)}</p><p>{e.text}</p></li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </div>
  );
}
