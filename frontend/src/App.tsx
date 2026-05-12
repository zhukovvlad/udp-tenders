import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster, toast } from "sonner";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import Dashboard from "@/pages/Dashboard";
import Projects from "@/pages/Projects";
import ProjectPage from "@/pages/ProjectPage";
import Suppliers from "@/pages/Suppliers";
import SupplierPage from "@/pages/SupplierPage";
import Materials from "@/pages/Materials";
import MaterialPage from "@/pages/MaterialPage";
import Reports from "@/pages/Reports";
import SettingsPage from "@/pages/Settings";
import Review from "@/pages/Review";

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

export default function App() {
  return (
    <ThemeProvider attribute="data-theme" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/projects/:id" element={<ProjectPage />} />
              <Route path="/suppliers" element={<Suppliers />} />
              <Route path="/suppliers/:slug" element={<SupplierPage />} />
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
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
