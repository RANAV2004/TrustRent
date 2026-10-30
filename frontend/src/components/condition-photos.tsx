"use client";
import { FormEvent, useEffect, useState } from "react";
import { ConditionPhoto, ConditionSet, getPhotos, photoBlobUrl, Stage, STAGE_LABEL, uploadPhoto } from "@/lib/condition";
const when = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
function Thumb({ depositId, p }: { depositId: string; p: ConditionPhoto }) { // photo tile
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let live = true;
    photoBlobUrl(depositId, p.id).then(
      (u) => { url = u; if (live) setSrc(u); else URL.revokeObjectURL(u); },
      (e) => live && setFailed(e.message),
    );
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [depositId, p.id]);
  return (
    <figure className="flex flex-col gap-1">
      <a href={src ?? undefined} target="_blank" rel="noopener noreferrer"
        className="block aspect-[4/3] overflow-hidden rounded-lg border border-line bg-mist">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={`${p.room}, ${STAGE_LABEL[p.stage]}, by the ${p.side}`} className="h-full w-full object-cover" />
        ) : (
          <span className="flex h-full items-center justify-center p-2 text-center text-xs text-muted">{failed ?? "Loading..."}</span>
        )}
      </a>
      <figcaption className="flex flex-col text-xs">
        <span><span className="font-medium capitalize">{p.side}</span>, {when(p.uploadedAt)}</span>
        {p.note && <span className="text-muted">{p.note}</span>}
        <span className={p.verified ? "text-vault" : "text-claim"} title={p.receipt ?? ""}>
          {p.verified ? "Fingerprint matches the receipt chain" : "Fingerprint mismatch"}
        </span>
      </figcaption>
    </figure>
  );
}
function UploadForm({ depositId, set, onAdded }: { depositId: string; set: ConditionSet; onAdded: (p: ConditionPhoto) => void }) { // add photos
  const open = (Object.keys(set.canUpload) as Stage[]).filter((s) => set.canUpload[s]);
  const [stage, setStage] = useState<Stage>(open[0]);
  const [room, setRoom] = useState(set.rooms[0]);
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!files.length) return setError("Choose at least one photo.");
    setError(null);
    const form = e.currentTarget;
    for (const [i, f] of files.entries()) {
      setBusy(`Uploading ${i + 1} of ${files.length}...`);
      try {
        onAdded(await uploadPhoto(depositId, stage, room, note, f));
      } catch (err) {
        setError(`${f.name}: ${err instanceof Error ? err.message : "upload failed"}`);
        break;
      }
    }
    setBusy(null);
    setFiles([]);
    setNote("");
    form.reset();
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-xl bg-mist p-4">
      <p className="text-sm font-medium">Add photos as the {set.side}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs text-muted">Stage</span>
          <select value={stage} onChange={(e) => setStage(e.target.value as Stage)} className="rounded-lg border border-line bg-surface px-3 py-2">
            {open.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs text-muted">Room</span>
          <select value={room} onChange={(e) => setRoom(e.target.value)} className="rounded-lg border border-line bg-surface px-3 py-2">
            {set.rooms.map((r) => <option key={r}>{r}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs text-muted">Note (optional)</span>
          <input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Crack near the window"
            className="rounded-lg border border-line bg-surface px-3 py-2" />
        </label>
      </div>
      <input type="file" accept="image/jpeg,image/png,image/webp" multiple
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))} className="text-sm" />
      <p className="text-xs text-muted">
        Photos can&apos;t be changed or deleted after upload. Each one gets a fingerprint in the receipt chain, and location data is removed.
      </p>
      <button type="submit" disabled={!!busy} className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep disabled:opacity-60">
        {busy ?? `Upload ${files.length > 1 ? `${files.length} photos` : "photo"}`}
      </button>
      {error && <p role="alert" className="text-sm text-claim">{error}</p>}
    </form>
  );
}
export function ConditionPhotos({ depositId }: { depositId: string }) { // room photos
  const [open, setOpen] = useState(false);
  const [set, setSet] = useState<ConditionSet | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open && !set) getPhotos(depositId).then(setSet, (e) => setError(e.message));
  }, [open, set, depositId]);
  const rooms = set ? set.rooms.filter((r) => set.photos.some((p) => p.room === r)) : [];
  const canAdd = set && (set.canUpload.move_in || set.canUpload.move_out);
  return (
    <section className="flex flex-col gap-3 border-t border-line pt-3">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="flex w-full items-center justify-between text-left text-sm font-medium">
        <span>{set?.compare === false ? "Your move-in and move-out photos" : "Move-in and move-out photos"}{set ? ` (${set.photos.length})` : ""}</span>
        <span className="text-vault">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        error ? <p role="alert" className="text-sm text-claim">{error}</p>
          : !set ? <p className="text-sm text-muted" role="status">Loading...</p>
            : (
              <div className="flex flex-col gap-4">
                <p className="text-xs text-muted">
                  {set.compare
                    ? "Photos from the tenant and the owner, room by room. Compare move-in with move-out before deciding a deduction."
                    : "Photograph each room at move-in and again at move-out. Only you and the TrustRent admin can see your photos. If there's a dispute, the admin compares them with the other side's photos."}
                </p>
                {canAdd && <UploadForm depositId={depositId} set={set} onAdded={(p) => setSet((s) => s && { ...s, photos: [...s.photos, p] })} />}
                {!rooms.length && <p className="text-sm text-muted">No photos yet.</p>}
                {rooms.map((room) => (
                  <div key={room} className="flex flex-col gap-2">
                    <h3 className="text-sm font-medium">{room}</h3>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {(["move_in", "move_out"] as Stage[]).map((stage) => {
                        const list = set.photos.filter((p) => p.room === room && p.stage === stage);
                        const groups = set.compare ? (["tenant", "owner"] as const) : ([set.side ?? "tenant"] as const);
                        return (
                          <div key={stage} className="flex flex-col gap-2 rounded-xl border border-line p-3">
                            <span className="text-xs font-medium text-muted uppercase">{STAGE_LABEL[stage]}</span>
                            {groups.map((side) => {
                              const mine = list.filter((p) => p.side === side);
                              return (
                                <div key={side} className="flex flex-col gap-1">
                                  {set.compare && <span className="text-xs font-medium capitalize">{side}</span>}
                                  {mine.length ? (
                                    <div className="grid grid-cols-2 gap-2">{mine.map((p) => <Thumb key={p.id} depositId={depositId} p={p} />)}</div>
                                  ) : <span className="text-xs text-muted">No photos</span>}
                                </div>
                              );
                            })}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )
      )}
    </section>
  );
}