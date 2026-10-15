import { useMemo } from "react";
import { useMaterialTypes } from "@/services/queries";
import type { MaterialType } from "@/types/unit";

/**
 * Подписи и варианты выбора типов материалов — из справочника `/api/material-types`
 * (`material_types.name`), чтобы новый тип появлялся в UI без правки фронта.
 * До загрузки и для неизвестного кода подпись — сам код. «Прочее» в списке последним.
 */
export function useMaterialTypeLabels(): {
  label: (code: string) => string;
  options: MaterialType[];
} {
  const { data } = useMaterialTypes();
  return useMemo(() => {
    const names = new Map((data ?? []).map((t) => [t.code, t.name]));
    const options = [...(data ?? [])].sort(
      (a, b) => Number(a.code === "other") - Number(b.code === "other"),
    );
    return { label: (code: string) => names.get(code) ?? code, options };
  }, [data]);
}
