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
