const copy = {
  almanac: {
    font: "Georgia, 'Iowan Old Style', serif",
    mono: "ui-monospace, monospace",
    bg: "#f4f0e6",
    ink: "#241c14",
    rule: "#c4b59a",
    open: "#2f5d45",
  },
  instrument: {
    font: "var(--font-sans), sans-serif",
    mono: "var(--font-spline), ui-monospace",
    bg: "#f7f8f8",
    ink: "#1c2430",
    rule: "#d5d8dc",
    open: "#1f6b4a",
  },
  civic: {
    font: "var(--font-sans), sans-serif",
    mono: "var(--font-spline), ui-monospace",
    bg: "#f6f1ea",
    ink: "#243028",
    rule: "#e2d5c8",
    open: "#3d6b4f",
  },
} as const;

export default async function DirectionPage({ params }: { params: Promise<{ direction: string }> }) {
  const { direction } = await params;
  const theme = copy[direction as keyof typeof copy] ?? copy.instrument;
  return (
    <div style={{ background: theme.bg, color: theme.ink, fontFamily: theme.font }} className="p-6">
      <p style={{ fontFamily: theme.mono }} className="text-xs">
        Layout sample · not an extra live notice
      </p>
      <h1 className="mt-4 text-3xl">SBEP joint call 2026</h1>
      <div className="mt-6 grid gap-6 border-t pt-4 md:grid-cols-[1fr_12rem]" style={{ borderColor: theme.rule }}>
        <div>
          <p className="text-sm">Sustainable Blue Economy Partnership · grant · two stages</p>
          <p className="mt-3 text-sm leading-6">
            Pre-proposals close on 16 November 2026 at 15:00 CET. Provisional budget EUR 37,041,760. The
            figure is extracted from the announcement, not estimated.
          </p>
        </div>
        <p style={{ fontFamily: theme.mono, color: theme.open }} className="text-sm">
          Closes in days
          <br />
          EUR 37,041,760
        </p>
      </div>
      <p className="mt-8 text-sm">No calls on this heading. 14 match if you drop TRL 6–8.</p>
    </div>
  );
}
