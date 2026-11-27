"use client";
import { useEffect, useMemo } from "react";
import { MAX_IMAGE_MB, MAX_IMAGES, STATUS_TONE, TicketImage, TicketStatus, useTicketImage } from "@/lib/support";

export function StatusPill({ status, label }: { status: TicketStatus; label: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${STATUS_TONE[status]}`}>{label}</span>;
}

function Thumb({ ticketNo, image }: { ticketNo: string; image: TicketImage }) {
  const url = useTicketImage(ticketNo, image.id);
  return (
    <a href={url ?? undefined} target="_blank" rel="noopener" aria-label={`Open ${image.fileName}`}
      className="block h-24 w-32 overflow-hidden rounded-lg border border-line bg-mist">
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={image.fileName} className="h-full w-full object-cover" />
      ) : <span className="grid h-full place-items-center text-xs text-muted">Loading...</span>}
    </a>
  );
}

export function Screenshots({ ticketNo, images }: { ticketNo: string; images: TicketImage[] }) {
  if (!images.length) return null;
  return <div className="flex flex-wrap gap-2">{images.map((i) => <Thumb key={i.id} ticketNo={ticketNo} image={i} />)}</div>;
}

export function ImagePicker({ files, onChange, id = "images" }: { files: File[]; onChange: (f: File[]) => void; id?: string }) {
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);
  const tooBig = files.find((f) => f.size > MAX_IMAGE_MB * 1024 * 1024);
  return (
    <div className="flex flex-col gap-2 text-sm">
      <label htmlFor={id} className="font-medium">Screenshots (optional)</label>
      <input id={id} type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={files.length >= MAX_IMAGES}
        onChange={(e) => { onChange([...files, ...Array.from(e.target.files ?? [])].slice(0, MAX_IMAGES)); e.target.value = ""; }}
        className="rounded-lg border border-line bg-surface px-3 py-2 file:mr-3 file:rounded-md file:border-0 file:bg-vault-soft file:px-2 file:py-1 file:text-vault disabled:opacity-60" />
      <span className={`text-xs ${tooBig ? "text-claim" : "text-muted"}`}>
        {tooBig ? `${tooBig.name} is larger than ${MAX_IMAGE_MB} MB.` : `Up to ${MAX_IMAGES} images (JPG, PNG or WebP), ${MAX_IMAGE_MB} MB each. Location data is removed.`}
      </span>
      {!!files.length && (
        <ul className="flex flex-wrap gap-2">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previews[i]} alt={f.name} className="h-20 w-28 rounded-lg border border-line object-cover" />
              <button type="button" onClick={() => onChange(files.filter((_, j) => j !== i))} aria-label={`Remove ${f.name}`}
                className="absolute -top-2 -right-2 grid h-6 w-6 place-items-center rounded-full bg-ink text-xs text-white">×</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
