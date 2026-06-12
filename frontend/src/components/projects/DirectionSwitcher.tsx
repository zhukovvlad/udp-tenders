import { cn } from "@/lib/utils";

interface DirectionSwitcherProps {
  directions: { code: string; name: string }[];
  /** 'all' | code направления */
  value: string;
  onChange: (code: string) => void;
}

/** Переключатель направлений (спека §3.1, §7.1). Скрыт у пустого объекта. */
export function DirectionSwitcher({ directions, value, onChange }: DirectionSwitcherProps) {
  if (directions.length === 0) return null;
  const items = [{ code: "all", name: "Все направления" }, ...directions];
  return (
    <div
      role="tablist"
      aria-label="Направления"
      data-testid="direction-switcher"
      className="inline-flex items-center gap-1 rounded-lg border border-border-subtle bg-surface-sunken p-1"
    >
      {items.map((d) => (
        <button
          key={d.code}
          type="button"
          role="tab"
          aria-selected={value === d.code}
          data-testid={`direction-${d.code}`}
          onClick={() => onChange(d.code)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm transition-colors",
            value === d.code
              ? "bg-surface text-fg shadow-sm"
              : "text-fg-secondary hover:text-fg",
          )}
        >
          {d.name}
        </button>
      ))}
    </div>
  );
}
