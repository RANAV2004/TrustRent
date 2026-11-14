"use client";
import { FormEvent, useEffect, useState } from "react";
import { addNote, Deposit, listNotes, Note } from "@/lib/deposits";

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export function NoteList({ notes }: { notes: Note[] }) {
  if (!notes.length) return <p className="text-sm text-muted">No statements yet.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {notes.map((n) => (
        <li key={n.id} className="rounded-lg bg-mist px-3 py-2 text-sm">
          <p className="text-xs text-muted"><span className="font-medium capitalize text-ink">{n.role === "admin" ? "TrustRent reviewer" : n.role}</span> · {n.author} · {when(n.at)}</p>
          <p className="whitespace-pre-line">{n.text}</p>
        </li>
      ))}
    </ul>
  );
}

export function DisputeNotes({ d }: { d: Deposit }) { // statements
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [canAdd, setCanAdd] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    listNotes(d.id).then((r) => { setNotes(r.notes); setCanAdd(r.canAdd); }, () => setNotes([]));
  }, [d.id, d.status]);
  if (!notes || (d.status !== "disputed" && d.status !== "settlement_proposed" && !notes.length)) return null;
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setNotes((await addNote(d.id, text)).notes);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the statement.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <h3 className="text-base font-medium">Statements</h3>
      <p className="text-xs text-muted">Explain your side. The other party and the TrustRent reviewer can read these.</p>
      <NoteList notes={notes} />
      {canAdd && (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000} placeholder="e.g. The crack in the counter was already there; see my move-in photo of the kitchen."
            className="rounded-lg border border-line bg-surface px-3 py-2 text-sm" />
          <button type="submit" disabled={busy || text.trim().length < 5} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">Add statement</button>
        </form>
      )}
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </section>
  );
}
