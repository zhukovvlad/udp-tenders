import { describe, it, expect, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router-dom";
import { http, HttpResponse } from "msw";

import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import AdminOrgDetail from "./AdminOrgDetail";
import type { User } from "@/types/auth";

const SUPERUSER: User = {
  id: 99,
  email: "root@platform.ru",
  org_id: null,
  org_role: null,
  is_superuser: true,
  organization: null,
};

function renderDetail() {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/organizations/:id" element={<AdminOrgDetail />} />
    </Routes>,
    { initialRoute: "/admin/organizations/1", initialUser: SUPERUSER },
  );
}

describe("AdminOrgDetail — редактирование организации", () => {
  it("кнопка «Редактировать» открывает диалог с предзаполненными полями", async () => {
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => expect(screen.getByText("ООО «СтройГрад»")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /Редактировать/ }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Название")).toHaveValue("ООО «СтройГрад»");
    expect(within(dialog).getByLabelText(/ИНН/)).toHaveValue("7705123456");
  });

  it("сохранение отправляет PATCH с изменёнными полями", async () => {
    const user = userEvent.setup();
    const onPatch = vi.fn();

    server.use(
      http.patch("/api/admin/organizations/:id", async ({ request, params }) => {
        const body = await request.json();
        onPatch({ id: params.id, body });
        return HttpResponse.json({ id: Number(params.id), name: "ООО Новое", inn: "7705123456", kind: "contractor" });
      }),
    );

    renderDetail();
    await waitFor(() => expect(screen.getByText("ООО «СтройГрад»")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /Редактировать/ }));
    const dialog = await screen.findByRole("dialog");

    const nameInput = within(dialog).getByLabelText("Название");
    await user.clear(nameInput);
    await user.type(nameInput, "ООО Новое");
    await user.click(within(dialog).getByRole("button", { name: /Подрядчик/ }));
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(onPatch).toHaveBeenCalledTimes(1));
    expect(onPatch.mock.calls[0][0].id).toBe("1");
    expect(onPatch.mock.calls[0][0].body).toMatchObject({ name: "ООО Новое", kind: "contractor" });
  });
});

describe("AdminOrgDetail — вкладки (shadcn Tabs)", () => {
  it("переключение на «Доступ к проектам» показывает форму выдачи доступа", async () => {
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => expect(screen.getByText("ООО «СтройГрад»")).toBeInTheDocument());

    // По умолчанию активна вкладка «Пользователи»
    expect(screen.getByText("Добавить пользователя")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Доступ к проектам/ }));

    await waitFor(() => {
      expect(screen.getByText("Дать доступ к проекту")).toBeInTheDocument();
    });
  });
});
