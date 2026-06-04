import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import { CorridorsTab } from "./CorridorsTab";

const CLASSES = [
  { id: 1, material_type: "concrete", name: "В25", created_at: "2026-01-01T00:00:00Z" },
  { id: 2, material_type: "rebar", name: "d12", created_at: "2026-01-01T00:00:00Z" },
];

function mockClasses() {
  server.use(http.get("/api/material-classes", () => HttpResponse.json(CLASSES)));
}

describe("CorridorsTab", () => {
  it("shows compensated class with its percent and non-compensated with add button", async () => {
    mockClasses();
    server.use(
      http.get("/api/projects/:projectId/compensation-corridors", () =>
        HttpResponse.json([
          { material_class_id: 1, material_class_name: "В25", material_type: "concrete", corridor_pct: 5 },
        ]),
      ),
    );

    renderWithProviders(<CorridorsTab projectId={42} />);

    expect(await screen.findByText("В25")).toBeInTheDocument();
    // compensated → shows 5%
    expect(await screen.findByText(/5%/)).toBeInTheDocument();
    // non-compensated rebar → shows the make-compensated affordance
    expect(await screen.findByText("d12")).toBeInTheDocument();
  });

  it("sends PUT when entering a percent for a non-compensated class", async () => {
    const onPut = vi.fn();
    mockClasses();
    server.use(
      http.get("/api/projects/:projectId/compensation-corridors", () => HttpResponse.json([])),
      http.put(
        "/api/projects/:projectId/compensation-corridors/:materialClassId",
        async ({ params, request }) => {
          onPut({ materialClassId: params.materialClassId, body: await request.json() });
          return HttpResponse.json({ material_class_id: 1, corridor_pct: 5 });
        },
      ),
    );

    renderWithProviders(<CorridorsTab projectId={42} />);

    const addButtons = await screen.findAllByRole("button", { name: /Сделать компенсируемым/ });
    await userEvent.click(addButtons[0]);
    const input = await screen.findByLabelText("Процент коридора");
    await userEvent.type(input, "5{Enter}");

    await waitFor(() => expect(onPut).toHaveBeenCalledWith({
      materialClassId: "1",
      body: { corridor_pct: 5 },
    }));
  });
});
