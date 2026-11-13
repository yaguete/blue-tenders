export function SectionKicker({ n, label }: { n: number; label: string }) {
  return (
    <p className="font-mono text-xs tracking-[0.16em] text-brand-blue uppercase">
      {String(n).padStart(2, "0")} / {label}
    </p>
  );
}
