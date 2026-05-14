// Three-state status badge: fresh / stale / missing (Phase 10-C-1)

import { cn } from "@/lib/utils";
import type { DataStatus } from "@/types/data";
import { STATUS_LABEL } from "@/types/data";

interface StatusBadgeProps {
  status: DataStatus;
  className?: string;
}

const DOT_CLASS: Record<DataStatus, string> = {
  fresh:   "bg-emerald-400",
  stale:   "bg-amber-400",
  missing: "bg-rose-400",
};

const BADGE_CLASS: Record<DataStatus, string> = {
  fresh:   "bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/30",
  stale:   "bg-amber-500/15  text-amber-300  ring-1 ring-inset ring-amber-500/30",
  missing: "bg-rose-500/15   text-rose-300   ring-1 ring-inset ring-rose-500/30",
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      data-testid={`status-badge-${status}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
        BADGE_CLASS[status],
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASS[status])} />
      {STATUS_LABEL[status]}
    </span>
  );
}
