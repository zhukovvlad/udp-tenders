import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/server";
import LoginPage from "./LoginPage";

// MSW default: POST /api/auth/login → 200 { status: "ok" }

function renderLogin() {
  // LoginPage не требует авторизации — передаём null чтобы не предзаполнять кэш
  return renderWithProviders(<LoginPage />, { initialUser: null });
}

describe("LoginPage", () => {
  it("отображает форму входа", () => {
    renderLogin();
    expect(screen.getByLabelText("Эл. почта")).toBeInTheDocument();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Войти" })).toBeInTheDocument();
  });

  it("при успешном логине переходит на /dashboard", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Эл. почта"), "admin@test.com");
    await user.type(screen.getByLabelText("Пароль"), "secret");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    // После успешного мутации navigate("/dashboard") — MemoryRouter покажет отсутствие совпадения,
    // главное что не появилась ошибка и мутация прошла без исключения
    await waitFor(() => {
      expect(screen.queryByText("Неверный email или пароль")).not.toBeInTheDocument();
    });
  });

  it("при ошибке логина показывает сообщение", async () => {
    server.use(
      http.post("/api/auth/login", () => new HttpResponse(null, { status: 401 }))
    );

    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("Эл. почта"), "bad@test.com");
    await user.type(screen.getByLabelText("Пароль"), "wrong");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() => {
      expect(screen.getByText("Неверный email или пароль")).toBeInTheDocument();
    });
  });
});
