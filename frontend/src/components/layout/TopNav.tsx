import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Building2, Users, Layers, FileSpreadsheet,
  Settings, LogOut, type LucideIcon,
} from "lucide-react";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "@/lib/utils";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NAV: { to: string; icon: LucideIcon; label: string; end?: boolean }[] = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Дашборд", end: true },
  { to: "/projects",  icon: Building2,       label: "Объекты" },
  { to: "/suppliers", icon: Users,           label: "Поставщики" },
  { to: "/materials", icon: Layers,          label: "Номенклатура" },
  { to: "/reports",   icon: FileSpreadsheet, label: "Отчёты" },
];

export function TopNav() {
  const navigate = useNavigate();
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
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-hover text-sm font-medium text-fg hover:bg-surface-hover/80">
              ЗВ
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                className="flex items-center gap-2"
                onClick={() => navigate("/settings")}
              >
                <Settings size={14} /> Настройки
              </DropdownMenuItem>
              <DropdownMenuItem className="flex items-center gap-2 text-fg-secondary">
                <LogOut size={14} /> Выйти
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
