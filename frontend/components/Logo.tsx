export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5 text-ink">
      <svg viewBox="0 0 32 32" aria-hidden="true" className="h-7 w-7">
        <rect width="32" height="32" rx="9" fill="#3978F6" />
        <rect x="6.5" y="13" width="2.4" height="6" rx="1.2" fill="#F3F5F8" />
        <rect x="10.6" y="10" width="2.4" height="12" rx="1.2" fill="#F3F5F8" />
        <rect x="14.8" y="7" width="2.4" height="18" rx="1.2" fill="#F3F5F8" />
        <rect x="19" y="10" width="2.4" height="12" rx="1.2" fill="#F3F5F8" />
        <rect x="23.1" y="13" width="2.4" height="6" rx="1.2" fill="#F3F5F8" />
      </svg>
      <span className="font-display text-[22px] leading-none tracking-[-0.05em]">tracktransfer</span>
    </span>
  );
}
