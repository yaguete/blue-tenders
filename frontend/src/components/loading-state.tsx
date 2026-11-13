import { cn } from "@/lib/utils";

type LoadingStateProps = {
  label: string;
  className?: string;
};

export function LoadingState({ label, className }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("inline-flex items-center gap-2.5 text-sm text-muted-foreground", className)}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        className="size-4 shrink-0 animate-spin text-accent-ink"
      >
        <circle
          cx="12"
          cy="12"
          r="9.5"
          stroke="currentColor"
          strokeOpacity="0.2"
          strokeWidth="2.25"
        />
        <path
          d="M21.5 12a9.5 9.5 0 0 0-6.6-9.05"
          stroke="currentColor"
          strokeWidth="2.25"
          strokeLinecap="round"
        />
      </svg>
      <span>{label}</span>
    </div>
  );
}
