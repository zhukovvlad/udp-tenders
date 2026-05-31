import api from "@/lib/api";
import type { ID } from "@/types/common";
import type {
  AdminOrgDetail,
  AdminOrgListItem,
  AdminUser,
  AdminUserCreateInput,
  AdminUserUpdateInput,
  AdminUsersPage,
  OrgCreateInput,
  OrgProjectLink,
  OrgUpdateInput,
  ProjectLinkInput,
  ResetPasswordResult,
} from "@/types/admin";

export const adminApi = {
  // --- Организации ---
  listOrganizations: (): Promise<AdminOrgListItem[]> =>
    api.get<AdminOrgListItem[]>("/admin/organizations").then((r) => r.data),

  getOrganization: (id: ID): Promise<AdminOrgDetail> =>
    api.get<AdminOrgDetail>(`/admin/organizations/${id}`).then((r) => r.data),

  createOrganization: (input: OrgCreateInput): Promise<AdminOrgListItem> =>
    api.post<AdminOrgListItem>("/admin/organizations", input).then((r) => r.data),

  updateOrganization: (id: ID, input: OrgUpdateInput): Promise<AdminOrgListItem> =>
    api.patch<AdminOrgListItem>(`/admin/organizations/${id}`, input).then((r) => r.data),

  // --- Пользователи ---
  createUser: (orgId: ID, input: AdminUserCreateInput): Promise<AdminUser> =>
    api.post<AdminUser>(`/admin/organizations/${orgId}/users`, input).then((r) => r.data),

  listUsers: (params?: { q?: string; page?: number; page_size?: number }): Promise<AdminUsersPage> =>
    api.get<AdminUsersPage>("/admin/users", { params }).then((r) => r.data),

  updateUser: (userId: ID, input: AdminUserUpdateInput): Promise<AdminUser> =>
    api.patch<AdminUser>(`/admin/users/${userId}`, input).then((r) => r.data),

  resetPassword: (userId: ID): Promise<ResetPasswordResult> =>
    api.post<ResetPasswordResult>(`/admin/users/${userId}/reset-password`).then((r) => r.data),

  // --- Доступ к проектам ---
  linkProject: (orgId: ID, input: ProjectLinkInput): Promise<OrgProjectLink> =>
    api.post<OrgProjectLink>(`/admin/organizations/${orgId}/projects`, input).then((r) => r.data),

  unlinkProject: (orgId: ID, projectId: ID): Promise<void> =>
    api.delete(`/admin/organizations/${orgId}/projects/${projectId}`).then(() => undefined),
};
