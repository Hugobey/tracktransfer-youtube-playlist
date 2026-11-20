export function StatusBadge({ label, tone }: { label: string; tone: string }) {
  const color =
    tone === "high" || tone === "selected"
      ? "border-blue/70 text-blue-2"
      : tone === "likely" || tone === "review"
        ? "border-warn/50 text-warn"
        : tone === "error" || tone === "none"
          ? "border-danger/50 text-danger-text"
          : "border-line-strong text-muted";
  return <span className={`inline-flex h-6 items-center border px-2 font-plex text-[10px] tracking-wide uppercase ${color}`}>{label}</span>;
}
