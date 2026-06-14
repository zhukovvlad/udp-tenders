import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface DirectionSwitcherProps {
  directions: { code: string; name: string }[];
  /** 'all' | code направления */
  value: string;
  onChange: (code: string) => void;
}

/**
 * Переключатель направлений (спека §3.1, §7.1). Скрыт у пустого объекта.
 * Сегментированный фильтр на shadcn-примитиве ToggleGroup (одиночный выбор):
 * семантика toggle (`aria-pressed`), а не tabs — у фильтра нет панелей.
 */
export function DirectionSwitcher({ directions, value, onChange }: DirectionSwitcherProps) {
  if (directions.length === 0) return null;
  const items = [{ code: "all", name: "Все направления" }, ...directions];
  return (
    <ToggleGroup
      aria-label="Направления"
      data-testid="direction-switcher"
      value={[value]}
      onValueChange={(vals) => {
        const next = vals[0];
        // Клик по уже активному сегменту снимает выбор (vals=[]) — игнорируем:
        // у фильтра всегда ровно одно активное направление.
        if (next) onChange(next);
      }}
    >
      {items.map((d) => (
        <ToggleGroupItem key={d.code} value={d.code} data-testid={`direction-${d.code}`}>
          {d.name}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
