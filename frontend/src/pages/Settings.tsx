import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { PageHeader } from "@/components/ui-domain/PageHeader";
import { Surface } from "@/components/ui-domain/Surface";
import { Button } from "@/components/ui-domain/Button";
import { Skeleton } from "@/components/ui-domain/Skeleton";

import { useSettings, useUpdateSettings } from "@/services/queries";
import type { AppSettings } from "@/services/api/settings";

type SectionKey = "general" | "parsing" | "about";

const SECTIONS: Array<{ key: SectionKey; label: string }> = [
  { key: "general", label: "Общие" },
  { key: "parsing", label: "Парсинг" },
  { key: "about", label: "О приложении" },
];

export default function SettingsPage() {
  const settingsQ = useSettings();
  const update = useUpdateSettings();

  const [active, setActive] = useState<SectionKey>("general");
  const [draft, setDraft] = useState<AppSettings | null>(null);

  useEffect(() => {
    if (settingsQ.data && !draft) setDraft(settingsQ.data);
  }, [settingsQ.data, draft]);

  const dirty = useMemo(() => {
    if (!draft || !settingsQ.data) return false;
    return JSON.stringify(draft) !== JSON.stringify(settingsQ.data);
  }, [draft, settingsQ.data]);

  if (settingsQ.isLoading || !draft) {
    return (
      <div className="container-page py-8 space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  return (
    <div className="container-page py-8">
      <PageHeader serif title="Настройки" subtitle="Параметры приложения и парсинга" />

      <div className="mt-6 grid grid-cols-12 gap-6">
        {/* Боковое меню */}
        <aside className="col-span-12 md:col-span-3">
          <nav className="md:sticky md:top-20 flex flex-row gap-1 md:flex-col">
            {SECTIONS.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setActive(s.key)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-left text-sm transition-colors duration-150",
                  active === s.key
                    ? "bg-surface-hover text-fg font-medium"
                    : "text-fg-secondary hover:bg-surface-hover hover:text-fg"
                )}
              >
                {s.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Контент */}
        <section className="col-span-12 md:col-span-9">
          {active === "general" && (
            <Surface>
              <h3 className="text-md font-medium">Общие</h3>
              <p className="mt-1 text-xs text-fg-tertiary">
                Базовые параметры приложения. Расширяется по мере добавления
                полей в backend.
              </p>
              <div className="mt-4 text-sm text-fg-secondary">
                Дополнительных параметров пока нет.
              </div>
            </Surface>
          )}

          {active === "parsing" && (
            <Surface>
              <h3 className="text-md font-medium">Парсинг ИИ</h3>
              <div className="mt-4 space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
                    Провайдер ИИ
                  </Label>
                  <Select
                    value={String(draft.ai_provider ?? "off")}
                    onValueChange={(v: string | null) =>
                      setDraft({ ...draft, ai_provider: (v ?? "off") as AppSettings["ai_provider"] })
                    }
                  >
                    <SelectTrigger className="w-[280px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openrouter">OpenRouter</SelectItem>
                      <SelectItem value="anthropic">Anthropic</SelectItem>
                      <SelectItem value="off">Отключено</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-fg-tertiary">
                    Сервис, который парсит таблицу позиций из СФ.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
                    Модель
                  </Label>
                  <Input
                    value={String(draft.ai_model ?? "")}
                    onChange={(e) => setDraft({ ...draft, ai_model: e.target.value })}
                    placeholder="например, anthropic/claude-haiku-4-5"
                    className="max-w-md"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
                    Порог уверенности (0..1)
                  </Label>
                  <Input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={String(draft.parse_threshold ?? 0.7)}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        parse_threshold: Number(e.target.value) || 0,
                      })
                    }
                    className="w-[160px]"
                  />
                  <p className="text-xs text-fg-tertiary">
                    Документы с уверенностью ниже порога отмечаются «требует
                    проверки».
                  </p>
                </div>
              </div>
            </Surface>
          )}

          {active === "about" && (
            <Surface>
              <h3 className="text-md font-medium">О приложении</h3>
              <div className="mt-4 space-y-1 text-sm text-fg-secondary">
                <div>УПД Трекер цен</div>
                <div>Версия: 2.0.0</div>
              </div>
            </Surface>
          )}
        </section>
      </div>

      {/* Sticky-bar */}
      {dirty && (
        <div className="sticky bottom-0 mt-8 -mx-6 border-t border-border-subtle bg-surface/95 px-6 py-3 backdrop-blur">
          <div className="container-page flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={() => setDraft(settingsQ.data ?? null)}>
              Отменить изменения
            </Button>
            <Button
              loading={update.isPending}
              onClick={() => update.mutate(draft)}
            >
              Сохранить
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
