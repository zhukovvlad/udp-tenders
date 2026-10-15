import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { AllProviders } from "@/test/utils";
import { useMaterialTypeLabels } from "./materialTypes";

const wrapper = ({ children }: { children: ReactNode }) => <AllProviders>{children}</AllProviders>;

describe("useMaterialTypeLabels", () => {
  it("labels types by their DB name, «Прочее» last in options", async () => {
    const { result } = renderHook(() => useMaterialTypeLabels(), { wrapper });

    await waitFor(() => expect(result.current.options.length).toBe(4));
    expect(result.current.label("mortar")).toBe("Раствор");
    expect(result.current.options.map((o) => o.code)).toEqual(["concrete", "rebar", "mortar", "other"]);
  });

  it("falls back to the raw code until types load or for unknown codes", () => {
    const { result } = renderHook(() => useMaterialTypeLabels(), { wrapper });

    expect(result.current.label("unknown")).toBe("unknown");
  });
});
