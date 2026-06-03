import api from "@/lib/api";
import type { ID } from "@/types/common";
import type { CompensationCorridor } from "@/types/compensationCorridor";

export const compensationCorridorsApi = {
  async list(projectId: ID): Promise<CompensationCorridor[]> {
    const { data } = await api.get<CompensationCorridor[]>(
      `/projects/${projectId}/compensation-corridors`,
    );
    return data;
  },
  async set(projectId: ID, materialClassId: ID, corridorPct: number): Promise<void> {
    await api.put(
      `/projects/${projectId}/compensation-corridors/${materialClassId}`,
      { corridor_pct: corridorPct },
    );
  },
  async remove(projectId: ID, materialClassId: ID): Promise<void> {
    await api.delete(`/projects/${projectId}/compensation-corridors/${materialClassId}`);
  },
};
