import Link from "next/link";

const directions = [
  ["almanac", "Almanac", "Paper, ink, a tide table."],
  ["instrument", "Instrument", "One accent. Figures first."],
  ["civic", "Civic warmth", "For a foundation, not a trading desk."],
];

export default function DesignLab() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Directions</h1>
      <p className="max-w-xl text-sm text-muted-foreground">
        The product currently uses Instrument. These screens are the other options, with the same call, so the
        choice is about type and colour, not about features. The choice is still open: see docs/design/decision.md.
      </p>
      <ul className="grid gap-4 md:grid-cols-3">
        {directions.map(([id, title, line]) => (
          <li key={id} className="border border-border p-4">
            <Link href={`/design-lab/${id}`} className="font-medium underline">
              {title}
            </Link>
            <p className="mt-2 text-sm text-muted-foreground">{line}</p>
          </li>
        ))}
      </ul>
      <Link href="/design-lab/system" className="text-sm underline">
        System
      </Link>
    </div>
  );
}
