import api from "@/lib/api";
import type {
  ReferencePrice,
  ReferencePriceCreateInput,
} from "@/types/referencePrice";
import type { ID } from "@/types/common";

export const referencePricesApi = {
  async list(projectId?: ID): Promise<ReferencePrice[]> {
    const { data } = await api.get<ReferencePrice[]>("/reference-prices", {
      params: projectId ? { project_id: projectId } : undefined,
    });
    return data;
  },
  async create(input: ReferencePriceCreateInput): Promise<ReferencePrice> {
    const { data } = await api.post<ReferencePrice>("/reference-prices", input);
    return data;
  },
  async remove(id: ID): Promise<void> {
    await api.delete(`/reference-prices/${id}`);
  },
};
