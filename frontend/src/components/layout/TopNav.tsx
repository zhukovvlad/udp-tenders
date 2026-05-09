import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Upload,
  Building2,
  Layers,
  Target,
  FileSpreadsheet,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Дашборд", end: true },
  { to: "/upload", icon: Upload, label: "Загрузка" },
  { to: "/projects", icon: Building2, label: "Объекты" },
  { to: "/material-classes", icon: Layers, label: "Классы материалов" },
  { to: "/reference-prices", icon: Target, label: "Эталоны" },
  { to: "/reports", icon: FileSpreadsheet, label: "Отчёты" },
  { to: "/settings", icon: Settings, label: "Настройки" },
];

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 h-14 border-b border-border-subtle bg-surface/95 backdrop-blur">
      <div className="container-page flex h-full items-center gap-6">
        <Logo />
        <nav className="flex flex-1 flex-wrap items-center gap-0.5">
          {NAV.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                  isActive
                    ? "bg-surface-hover text-fg"
                    : "text-fg-secondary hover:bg-surface-hover hover:text-fg"
                )
              }
            >
              <Icon size={14} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
