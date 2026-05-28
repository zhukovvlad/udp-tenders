import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster, toast } from "sonner";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useParams } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useCurrentUser } from "@/hooks/useAuth";
import Dashboard from "@/pages/Dashboard";
import LoginPage from "@/pages/LoginPage";
import MaterialPage from "@/pages/MaterialPage";
import Materials from "@/pages/Materials";
import ProjectPage from "@/pages/ProjectPage";
import Projects from "@/pages/Projects";
import Reports from "@/pages/Reports";
import Review from "@/pages/Review";
import SettingsPage from "@/pages/Settings";
import SupplierPage from "@/pages/SupplierPage";
import Suppliers from "@/pages/Suppliers";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 60_000, refetchOnWindowFocus: false },
    mutations: {
      onError: (error: unknown) => {
        toast.error(error instanceof Error ? error.message : "Произошла ошибка");
      },
    },
  },
});

/**
 * Layout-компонент: проверяет наличие авторизованного пользователя.
 * Пока идёт загрузка — ничего не рендерим (избегаем мигания).
 * При ошибке или отсутствии user — редирект на /login.
 */
function ProtectedLayout() {
  const { data: user, isLoading, isError } = useCurrentUser();
  if (isLoading) return null;
  if (isError || !user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/**
 * Обёртка для ProjectPage: передаёт key={id} чтобы при смене проекта
 * компонент пересоздавался и state сбрасывался автоматически.
 */
function ProjectPageWrapper() {
  const { id } = useParams<{ id: string }>();
  return <ProjectPage key={id} />;
}

export default function App() {
  return (
    <ThemeProvider attribute="data-theme" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
      <TooltipProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedLayout />}>
              <Route element={<AppShell />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/projects" element={<Projects />} />
                <Route path="/projects/:id" element={<ProjectPageWrapper />} />
                <Route path="/suppliers" element={<Suppliers />} />
                <Route path="/suppliers/:id" element={<SupplierPage />} />
                <Route path="/materials" element={<Materials />} />
                <Route path="/materials/:id" element={<MaterialPage />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/documents/:id" element={<Review />} />
                <Route path="/upload" element={<Navigate to="/projects" replace />} />
                <Route path="/material-classes" element={<Navigate to="/materials" replace />} />
                <Route path="/reference-prices" element={<Navigate to="/projects" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}

