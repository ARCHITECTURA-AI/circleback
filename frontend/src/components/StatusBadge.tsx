type Status =
  | "open"
  | "at_risk"
  | "overdue"
  | "fulfilled"
  | "renegotiated"
  | "dismissed"
  | "needs_clarification";

const STATUS_CONFIG: Record<Status, { label: string; color: string; bg: string; dot: string }> = {
  open: {
    label: "Open",
    color: "text-blue-700 dark:text-blue-300",
    bg: "bg-blue-50 dark:bg-blue-950/40",
    dot: "bg-blue-500",
  },
  at_risk: {
    label: "At Risk",
    color: "text-amber-700 dark:text-amber-300",
    bg: "bg-amber-50 dark:bg-amber-950/40",
    dot: "bg-amber-500",
  },
  overdue: {
    label: "Overdue",
    color: "text-red-700 dark:text-red-300",
    bg: "bg-red-50 dark:bg-red-950/40",
    dot: "bg-red-500",
  },
  fulfilled: {
    label: "Fulfilled",
    color: "text-emerald-700 dark:text-emerald-300",
    bg: "bg-emerald-50 dark:bg-emerald-950/40",
    dot: "bg-emerald-500",
  },
  renegotiated: {
    label: "Renegotiated",
    color: "text-violet-700 dark:text-violet-300",
    bg: "bg-violet-50 dark:bg-violet-950/40",
    dot: "bg-violet-500",
  },
  dismissed: {
    label: "Dismissed",
    color: "text-slate-600 dark:text-slate-400",
    bg: "bg-slate-100 dark:bg-slate-800",
    dot: "bg-slate-400",
  },
  needs_clarification: {
    label: "Needs Clarification",
    color: "text-orange-700 dark:text-orange-300",
    bg: "bg-orange-50 dark:bg-orange-950/40",
    dot: "bg-orange-500",
  },
};

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "md" }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status as Status] || STATUS_CONFIG.open;
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.bg} ${config.color} ${sizeClasses}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
}
