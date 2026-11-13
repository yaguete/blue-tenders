const pairs = [
  ["Background / text", "bg-background text-foreground"],
  ["Open", "text-status-open"],
  ["Soon", "text-status-soon"],
  ["Urgent", "text-status-urgent"],
];

export default function SystemPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">System</h1>
      <p className="max-w-xl text-sm text-muted-foreground">
        Tokens live in globals.css. Status is never colour alone: the word is in the label. Body text on the
        page background is the pair to check for AA. Dark mode is the Theme control in the header.
      </p>
      <ul className="space-y-3 text-sm">
        {pairs.map(([name, cls]) => (
          <li key={name} className={`border border-border p-3 ${cls}`}>
            {name} — Open calls close on a date.
          </li>
        ))}
      </ul>
      <p className="font-mono text-sm tabular">760071-2026 · EUR 4,000,000 · 29 Nov 2026, 23:59</p>
    </div>
  );
}
