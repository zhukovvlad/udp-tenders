import type { QueryCacheNotifyEvent, QueryClient } from "@tanstack/react-query";

import { NON_TERMINAL_STATUSES } from "./processingRefetchInterval";

const TERMINAL_STATUSES: ReadonlySet<string> = new Set(["parsed", "error"]);

type DocLike = { id?: number | string; status?: string };

/**
 * Детектор терминального перехода (S1-7, спека §5): одна общая Map<docId, status>
 * на приложение. Обрабатывает только updated-события квери documents (list) /
 * document (detail); data нормализуется к массиву; Map обновляется ДО
 * invalidateQueries; первое наблюдение документа переходом не считается.
 *
 * Семантика — AT-LEAST-ONCE (спека §5 п.5): запоздалый out-of-order ответ
 * (in-flight detail-запрос со старым processing, донесённый после перехода)
 * откатывает Map, и следующий свежий ответ даёт ПОВТОРНУЮ инвалидацию.
 * Это осознанно допустимо: инвалидация идемпотентна, цена — лишний refetch
 * в редкой гонке. Блокировать откат нельзя — легитимный даунгрейд
 * (новый reparse: parsed → processing) обязан записываться, иначе следующий
 * терминальный переход не сработает; отличить их на этом уровне нечем.
 */
export function createTerminalTransitionListener(queryClient: QueryClient) {
  const lastStatus = new Map<number | string, string>();

  return (event: QueryCacheNotifyEvent): void => {
    if (event.type !== "updated") return;
    const key0 = event.query.queryKey[0];
    if (key0 !== "documents" && key0 !== "document") return;

    const data: unknown = event.query.state.data;
    const docs: DocLike[] = Array.isArray(data) ? data : data ? [data as DocLike] : [];
    for (const doc of docs) {
      if (doc?.id === undefined || !doc.status) continue;
      const prev = lastStatus.get(doc.id);
      lastStatus.set(doc.id, doc.status); // до invalidate — иначе синхронный ре-репорт задвоит
      if (prev !== undefined && NON_TERMINAL_STATUSES.has(prev) && TERMINAL_STATUSES.has(doc.status)) {
        // Терминальный переход: свежие данные нужны спискам, карточке и dashboard.
        // Операционного тоста НЕТ — детектор не знает, какая операция шла (спека §5).
        // ["dashboard"] префиксом целиком, а не по-проектно — ОСОЗНАННОЕ упрощение
        // относительно спеки §5 п.5: projectId лежит в трёх семействах dashboard-ключей
        // на разных позициях, точечная инвалидация потребовала бы predicate по трём
        // формам; цена префикса — лишний refetch дашборда другого проекта, если тот
        // вдруг смонтирован. Существующие мутации инвалидируют так же.
        queryClient.invalidateQueries({ queryKey: ["documents"] });
        queryClient.invalidateQueries({ queryKey: ["document", doc.id] });
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      }
    }
  };
}

let subscribed = false;

/**
 * Единственная подписка детектора на QueryCache. Повторный вызов (HMR) — no-op;
 * возвращённый cleanup снимает подписку и разрешает новую.
 */
export function subscribeTerminalTransitions(queryClient: QueryClient): () => void {
  if (subscribed) return () => {};
  subscribed = true;
  const unsubscribe = queryClient
    .getQueryCache()
    .subscribe(createTerminalTransitionListener(queryClient));
  return () => {
    subscribed = false;
    unsubscribe();
  };
}
