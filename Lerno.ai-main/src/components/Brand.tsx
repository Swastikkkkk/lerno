/** ExplAInr brand: the bubble-and-play mark plus the wordmark with a bold "AI". */
export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden>
      <rect width="64" height="64" rx="15" fill="#0a0a0a" />
      <rect x="0.75" y="0.75" width="62.5" height="62.5" rx="14.25" fill="none" stroke="#fff" strokeOpacity=".14" strokeWidth="1.5" />
      <path d="M20 14h24a8 8 0 0 1 8 8v14a8 8 0 0 1-8 8H31l-9 7v-7h-2a8 8 0 0 1-8-8V22a8 8 0 0 1 8-8z" fill="none" stroke="#fff" strokeWidth="3.6" strokeLinejoin="round" />
      <path d="M28.5 22.5v13l10.5-6.5z" fill="#fff" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`tracking-tight text-white ${className}`} aria-label="ExplAInr">
      <span className="font-medium text-neutral-200">Expl</span>
      <span className="font-extrabold text-white">AI</span>
      <span className="font-medium text-neutral-200">nr</span>
    </span>
  );
}

export default function Brand({ size = 28, className = "", textClass = "text-[17px]" }: { size?: number; className?: string; textClass?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <LogoMark size={size} />
      <Wordmark className={textClass} />
    </span>
  );
}
