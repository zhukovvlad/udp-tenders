---
applyTo: "frontend/**"
---
# Frontend

- TS strict. UI — из `@/components/ui/`; доменные обёртки — `@/components/ui-domain/` (Button, Skeleton, EmptyState и т.д.).
- Контейнеры таблиц — `<Surface padding="none" className="overflow-x-auto">`, не самописные классы. Инпуты с иконками/аддонами — `InputGroupInput` + `InputGroupAddon`, не позиционирование иконок над голым `<input>`.
- Цвета — только семантические CSS-vars (`--color-fg`, `--color-bg`, `--color-surface`, `--color-accent`, …), не сырые.
- Все подписи UI — на русском (это русскоязычный продукт). Числа — `formatMoney` / `formatNumber` / `pluralRu` из `@/lib/format`; месяцы — `MONTH_NAMES_RU` из `@/lib/constants`.
- TanStack Query: запросы в `services/queries.ts`, ключи в `services/queryKeys.ts`.
- Фильтры уровня страницы — состояние в URL (`useSearchParams`), не локальный `useState`: шарабельные ссылки + back/forward. Образец — `ProjectPage` (направления): трёхзначное `undefined | 'all' | code`, зависимые запросы гейтятся (`{ enabled }`) до прихода данных, чтобы не уходить с непровалидированным значением.
- Одиночный сегмент-фильтр — `ToggleGroup` из `@/components/ui/toggle-group` (семантика toggle/`aria-pressed`, не tabs — у фильтра нет панелей), не самописный набор кнопок.
- Тесты — MSW v2 (`src/test/server.ts` + `handlers.ts`), `onUnhandledRequest: "error"`: добавляй handler на каждый новый эндпоинт. Бинарные эндпоинты — `HttpResponse.arrayBuffer(...)`, не `.json(...)`. Рендер — `renderWithProviders` из `src/test/utils.tsx` (принимает `initialUser`).
- Компонентные тесты лежат рядом с компонентом; страничные — в `src/pages/*.test.tsx`.

Гочи recharts/base-ui (дубль текста в служебном span → `getAllByText(...)[0]`; `Cell` без DOM → кастомный `shape` на `Bar`; `Tooltip.Trigger` без `asChild`; `TooltipProvider` нужен и в `App.tsx`, и в `AllProviders`) — подробности в `docs/testing.md`.
