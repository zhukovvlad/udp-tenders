import { Building2, Truck } from "lucide-react";
import type { OrgKind, OrgRole } from "@/types/auth";

/** Бейдж роли организации: заказчик / подрядчик. */
export function OrgKindBadge({ kind }: { kind: OrgKind | null | undefined }) {
  if (kind === "contractor") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-sunken px-2 py-0.5 text-xs font-medium text-fg-secondary">
        <Truck size={12} />
        Подрядчик
      </span>
    );
  }
  if (kind === "customer") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/15 px-2 py-0.5 text-xs font-medium text-accent">
        <Building2 size={12} />
        Заказчик
      </span>
    );
  }
  return <span className="text-fg-tertiary">—</span>;
}

const ROLE_STYLE: Record<OrgRole, string> = {
  // superadmin — фиолетовый, admin — синий, member — серый
  superadmin: "bg-[#EEEDFE] text-[#3C3489] dark:bg-violet-950 dark:text-violet-300",
  admin: "bg-[#E6F1FB] text-[#0C447C] dark:bg-blue-950 dark:text-blue-300",
  member: "bg-surface-sunken text-fg-secondary",
};

/** Бейдж роли пользователя внутри организации. */
export function OrgRoleBadge({ role }: { role: OrgRole | null | undefined }) {
  if (!role) return <span className="text-fg-tertiary">—</span>;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_STYLE[role]}`}>
      {role}
    </span>
  );
}
