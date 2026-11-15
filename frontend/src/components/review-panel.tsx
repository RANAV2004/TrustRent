"use client";
import { FormEvent, useEffect, useState } from "react";
import { Deposit } from "@/lib/deposits";
import { leaveReview, ReviewItem, ReviewState, reviewState } from "@/lib/trust";

export function Stars({ value, size = "text-base" }: { value: number; size?: string }) {
  return (
    <span className={`${size} tracking-tight text-amber`} aria-label={`${value} out of 5`}>
      {"★★★★★".slice(0, Math.round(value))}<span className="text-line">{"★★★★★".slice(Math.round(value))}</span>
    </span>
  );
}

function Quote({ r, label }: { r: ReviewItem; label: string }) {
  return (
    <div className="rounded-lg bg-mist px-3 py-2 text-sm">
      <p className="text-xs text-muted">{label}</p>
      <Stars value={r.rating} />
      {r.text && <p>{r.text}</p>}
    </div>
  );
}

export function ReviewPanel({ d }: { d: Deposit }) { // review after settlement
  const [s, setS] = useState<ReviewState | null>(null);
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (d.status === "settled") reviewState(d.id).then(setS, () => setS(null));
  }, [d.id, d.status]);
  if (!s || (!s.canReview && !s.mine && !s.theirs)) return null;
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!rating) return setError("Choose 1 to 5 stars.");
    try {
      setS(await leaveReview(d.id, rating, text));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the review.");
    }
  }
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <h3 className="text-base font-medium">Review {s.about}</h3>
      {s.canReview && (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <div className="flex gap-1" role="radiogroup" aria-label="Rating">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} star${n > 1 ? "s" : ""}`}
                onClick={() => setRating(n)} className={`text-2xl ${n <= rating ? "text-amber" : "text-line"} hover:text-amber`}>★</button>
            ))}
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} rows={2}
            placeholder="How was the tenancy and the deposit return?" className="rounded-lg border border-line px-3 py-2 text-sm" />
          <p className="text-xs text-muted">Reviews stay hidden until both of you review, or {s.reviewBy ? new Date(s.reviewBy).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "the review period ends"}, so nobody reviews in reply.</p>
          <button type="submit" className="w-fit rounded-lg bg-vault px-4 py-2 text-sm font-medium text-white hover:bg-vault-deep">Post review</button>
          {error && <p role="alert" className="text-sm text-claim">{error}</p>}
        </form>
      )}
      {s.mine && <Quote r={s.mine} label="Your review" />}
      {s.theirs ? <Quote r={s.theirs} label={`${s.about}'s review of you`} /> : s.theirsWaiting && <p className="text-sm text-muted">{s.about} reviewed you. Add your review to see it.</p>}
    </section>
  );
}
