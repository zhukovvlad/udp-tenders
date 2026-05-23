/**
 * Axios-клиент с поддержкой:
 * - httpOnly cookie аутентификации (withCredentials)
 * - CSRF double-submit (X-CSRF-Token заголовок для state-changing запросов)
 * - Автоматического refresh access-токена при 401
 */
import axios from "axios";

/** Читает значение куки по имени. */
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

const api = axios.create({
  baseURL: "/api",
  withCredentials: true, // cookie шлётся автоматически при каждом запросе
});

// CSRF: добавляем X-CSRF-Token для всех state-changing методов
api.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase();
  if (method && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = getCookie("csrf_token");
    if (csrf) {
      config.headers["X-CSRF-Token"] = csrf;
    }
  }
  return config;
});

// Авто-refresh: при 401 пробуем обновить access-токен и повторяем запрос
let refreshing: Promise<void> | null = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (
      error.response?.status === 401 &&
      !original._retry &&
      original.url !== "/auth/refresh" &&
      original.url !== "/auth/login"
    ) {
      original._retry = true;
      try {
        refreshing =
          refreshing ??
          api.post("/auth/refresh").then(() => {
            refreshing = null;
          });
        await refreshing;
        return api(original);
      } catch {
        // Refresh тоже не удался — перенаправить на логин
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
