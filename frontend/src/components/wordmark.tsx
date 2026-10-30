export function Wordmark({ className = "text-[22px]" }: { className?: string }) { // wordmark
  return (
    <span className={`font-brand leading-none font-bold ${className}`}>
      Trust<span style={{ color: "var(--logo-rent, #0d5b4c)" }}>Rent</span>
    </span>
  );
}
