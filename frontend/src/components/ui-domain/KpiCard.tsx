import type { ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  delta?: { value: string; tone: "up" | "down" | "neutral" };
  suffix?: ReactNode;
  valueClassName?: string;
  className?: string;
  breakdown?: { label: string; value: string }[];
}

export function KpiCard({ label, value, delta, suffix, valueClassName, className, breakdown }: KpiCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border-subtle bg-surface p-5",
        className
      )}
    >
      <div className="text-2xs uppercase tracking-wider text-fg-tertiary">
        {label}
      </div>
      <div className={cn("mt-2 font-mono text-2xl text-fg", valueClassName)}>
        {value}
        {suffix && <span className="ml-1.5 text-sm font-normal text-fg-secondary">{suffix}</span>}
      </div>
      {breakdown && breakdown.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {breakdown.map((b) => (
            <div key={b.label} className="flex items-center justify-between gap-2 text-xs text-fg-tertiary">
              <span>{b.label}</span>
              <span className="font-mono">{b.value}</span>
            </div>
          ))}
        </div>
      )}
      {delta && (
        <div
          className={cn(
            "mt-1 inline-flex items-center gap-1 text-xs",
            delta.tone === "up" && "text-warning",
            delta.tone === "down" && "text-accent",
            delta.tone === "neutral" && "text-fg-tertiary"
          )}
        >
          {delta.tone === "up" && <ArrowUp size={12} />}
          {delta.tone === "down" && <ArrowDown size={12} />}
          {delta.value}
        </div>
      )}
    </div>
  );
}
