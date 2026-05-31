/** Типы для аутентификации и профиля пользователя. */

/** Роль организации: заказчик / подрядчик. */
export type OrgKind = "customer" | "contractor";

export interface Organization {
  id: number;
  name: string;
  inn: string | null;
  kind?: OrgKind | null;
}

export type OrgRole = "superadmin" | "admin" | "member";

export interface User {
  id: number;
  email: string;
  org_id: number | null;
  org_role: OrgRole | null;
  is_superuser: boolean;
  organization: Organization | null;
}
