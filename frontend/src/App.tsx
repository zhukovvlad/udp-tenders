import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster, toast } from "sonner";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import Dashboard from "@/pages/Dashboard";
import UploadPage from "@/pages/Upload";
import Review from "@/pages/Review";
import Projects from "@/pages/Projects";
import MaterialClasses from "@/pages/MaterialClasses";
import ReferencePrices from "@/pages/ReferencePrices";
import Reports from "@/pages/Reports";
import SettingsPage from "@/pages/Settings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
    mutations: {
      onError: (error: unknown) => {
        const message =
          error instanceof Error ? error.message : "Произошла ошибка";
        toast.error(message);
      },
    },
  },
});

export default function App() {
  return (
    <ThemeProvider
      attribute="data-theme"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/material-classes" element={<MaterialClasses />} />
              <Route path="/reference-prices" element={<ReferencePrices />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/documents/:id" element={<Review />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
