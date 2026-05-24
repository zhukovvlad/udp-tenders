import api from "@/lib/api";
import type {
  Project,
  ProjectCreateInput,
  ProjectUpdateInput,
} from "@/types/project";
import type { ID } from "@/types/common";

export interface ProjectSupplier {
  id: number;
  name: string;
  inn: string | null;
  invoice_count: number;
}

export const projectsApi = {
  async list(): Promise<Project[]> {
    const { data } = await api.get<Project[]>("/projects");
    return data;
  },
  async create(input: ProjectCreateInput): Promise<Project> {
    const { data } = await api.post<Project>("/projects", input);
    return data;
  },
  async update(id: ID, input: ProjectUpdateInput): Promise<Project> {
    const { data } = await api.put<Project>(`/projects/${id}`, input);
    return data;
  },
  async remove(id: ID): Promise<void> {
    await api.delete(`/projects/${id}`);
  },
  async getSuppliers(projectId: ID): Promise<ProjectSupplier[]> {
    const { data } = await api.get<ProjectSupplier[]>(`/projects/${projectId}/suppliers`);
    return data;
  },
  async getSupplierExclusions(projectId: ID): Promise<number[]> {
    const { data } = await api.get<number[]>(`/projects/${projectId}/supplier-exclusions`);
    return data;
  },
  async addSupplierExclusion(projectId: ID, supplierId: ID, reason?: string): Promise<void> {
    await api.post(`/projects/${projectId}/supplier-exclusions/${supplierId}`, { reason: reason ?? null });
  },
  async removeSupplierExclusion(projectId: ID, supplierId: ID): Promise<void> {
    await api.delete(`/projects/${projectId}/supplier-exclusions/${supplierId}`);
  },
};
