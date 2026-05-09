import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Upload,
  Building2,
  Layers,
  Target,
  FileSpreadsheet,
  Settings,
} from "lucide-react";

import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/Upload";
import Review from "./pages/Review";
import Projects from "./pages/Projects";
import MaterialClasses from "./pages/MaterialClasses";
import ReferencePrices from "./pages/ReferencePrices";
import Reports from "./pages/Reports";
import SettingsPage from "./pages/Settings";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Дашборд" },
  { to: "/upload", icon: Upload, label: "Загрузка" },
  { to: "/projects", icon: Building2, label: "Объекты" },
  { to: "/material-classes", icon: Layers, label: "Классы материалов" },
  { to: "/reference-prices", icon: Target, label: "Эталоны" },
  { to: "/reports", icon: FileSpreadsheet, label: "Отчёты" },
  { to: "/settings", icon: Settings, label: "Настройки" },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background">
        <header className="border-b bg-card">
          <div className="container mx-auto flex h-14 items-center px-4">
            <h1 className="text-lg font-bold mr-8">УПД Трекер</h1>
            <nav className="flex gap-1 flex-wrap">
              {navItems.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    }`
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
        </header>

        <main className="container mx-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/material-classes" element={<MaterialClasses />} />
            <Route path="/reference-prices" element={<ReferencePrices />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/documents/:id" element={<Review />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
