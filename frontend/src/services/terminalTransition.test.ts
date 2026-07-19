import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTerminalTransitionListener } from "./terminalTransition";

/** Собирает updated-событие QueryCache с заданными queryKey и data. */
function updatedEvent(queryKey: readonly unknown[], data: unknown) {
  return { type: "updated", query: { queryKey, state: { data } } } as never;
}

describe("terminal transition detector (S1-7, спека §5)", () => {
  let qc: QueryClient;
  let invalidate: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    qc = new QueryClient();
    invalidate = vi.fn();
    qc.invalidateQueries = invalidate as never;
  });

  it("переход processing→parsed в одной квери → инвалидация ровно один раз", () => {
    const listen = createTerminalTransitionListener(qc);
    listen(updatedEvent(["documents", 1], [{ id: 7, project_id: 1, status: "processing" }]));
    expect(invalidate).not.toHaveBeenCalled();
    listen(updatedEvent(["documents", 1], [{ id: 7, project_id: 1, status: "parsed" }]));
    // 3 вызова = documents + document + dashboard за ОДИН переход
    expect(invalidate).toHaveBeenCalledTimes(3);
  });

  it("тот же переход из list- И detail-квери → всё равно один набор инвалидаций (общая Map)", () => {
    const listen = createTerminalTransitionListener(qc);
    listen(updatedEvent(["documents", 1], [{ id: 7, project_id: 1, status: "processing" }]));
    listen(updatedEvent(["document", 7], { id: 7, project_id: 1, status: "processing" }));
    listen(updatedEvent(["documents", 1], [{ id: 7, project_id: 1, status: "parsed" }]));
    listen(updatedEvent(["document", 7], { id: 7, project_id: 1, status: "parsed" }));
    expect(invalidate).toHaveBeenCalledTimes(3); // не 6: второй репорт видит обновлённую Map
  });

  it("первое наблюдение терминального документа → ноль инвалидаций", () => {
    const listen = createTerminalTransitionListener(qc);
    listen(updatedEvent(["documents", 1], [{ id: 7, project_id: 1, status: "parsed" }]));
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("чужие квери игнорируются", () => {
    const listen = createTerminalTransitionListener(qc);
    listen(updatedEvent(["dashboard", "summary", 1], [{ id: 7, status: "processing" }]));
    listen(updatedEvent(["dashboard", "summary", 1], [{ id: 7, status: "parsed" }]));
    expect(invalidate).not.toHaveBeenCalled();
  });
});

describe("сеяние 202-ответа в кэш (Codex P2 fix 1)", () => {
  it("setQueryData(processing) затем setQueryData(parsed) на реальном QueryCache → терминальная инвалидация ровно один набор", () => {
    // Реальный QueryClient (не мок invalidateQueries) + реальная подписка на
    // QueryCache — воспроизводит ровно тот путь, которым идёт мутация: сначала
    // onSuccess пишет 202-снапшот через qc.setQueryData (a не invalidateQueries),
    // и это должно синхронно дать "updated"-событие в QueryCache, которое
    // детектор увидит и запишет "processing" в свою Map ДО того, как фоновая
    // обработка завершится и следующий ответ придёт уже как "parsed".
    const realQc = new QueryClient();
    const invalidateSpy = vi.spyOn(realQc, "invalidateQueries");
    realQc.getQueryCache().subscribe(createTerminalTransitionListener(realQc));

    // Мутация (reparse/deskew/upload) сеет 202-ответ первой строкой onSuccess.
    realQc.setQueryData(["document", 7], { id: 7, project_id: 1, status: "processing" });
    expect(invalidateSpy).not.toHaveBeenCalled();

    // Быстрая обработка завершилась до первого polling-рефетча — тот приходит
    // уже терминальным.
    realQc.setQueryData(["document", 7], { id: 7, project_id: 1, status: "parsed" });

    // 3 = documents + document + dashboard, за один переход (не 0, как было бы
    // без сеяния 202, когда "parsed" оказался бы первым наблюдением документа).
    expect(invalidateSpy).toHaveBeenCalledTimes(3);
  });
});
