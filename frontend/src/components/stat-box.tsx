type StatBoxProps = {
  label: string;
  value: string;
  note?: string;
  onClick?: () => void;
};

const cell = "border border-border bg-card px-3 py-3 text-left sm:px-4";

export function StatBox({ label, value, note, onClick }: StatBoxProps) {
  const body = (
    <>
      <p className="font-mono text-xs leading-4 text-muted-foreground">{label}</p>
      <p className="mt-1.5 flex min-h-7 flex-wrap items-baseline gap-x-2">
        <span className="tabular text-xl font-medium leading-7">{value}</span>
        <span className="min-h-4 text-xs leading-4 text-muted-foreground">{note ?? ""}</span>
      </p>
    </>
  );
  if (!onClick) return <div className={cell}>{body}</div>;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${cell} cursor-pointer hover:bg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring`}
    >
      {body}
    </button>
  );
}
