/** Типы для аутентификации и профиля пользователя. */

export interface Organization {
  id: number;
  name: string;
  inn: string | null;
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
