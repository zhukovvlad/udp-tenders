import api from "@/lib/api";
import type {
  Project,
  ProjectCreateInput,
  ProjectUpdateInput,
} from "@/types/project";
import type { ID } from "@/types/common";

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
};
