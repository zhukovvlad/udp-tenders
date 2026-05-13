import api from "@/lib/api";
import type {
  ReferencePrice,
  ReferencePriceCreateInput,
} from "@/types/referencePrice";
import type { ID } from "@/types/common";

export const referencePricesApi = {
  async list(projectId?: ID, materialClassId?: ID): Promise<ReferencePrice[]> {
    const params: Record<string, unknown> = {};
    if (projectId) params.project_id = projectId;
    if (materialClassId) params.material_class_id = materialClassId;
    const { data } = await api.get<ReferencePrice[]>("/reference-prices", {
      params: Object.keys(params).length ? params : undefined,
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
