import api from "@/lib/api";
import type {
  AutoCalculateResponse,
  CalculateInput,
  DashboardCalculation,
  DashboardInvoices,
  DashboardSummary,
} from "@/types/dashboard";
import type { ID } from "@/types/common";

export const dashboardApi = {
  async summary(projectId: ID): Promise<DashboardSummary> {
    const { data } = await api.get<DashboardSummary>("/dashboard/summary", {
      params: { project_id: projectId },
    });
    return data;
  },
  async invoices(projectId: ID): Promise<DashboardInvoices> {
    const { data } = await api.get<DashboardInvoices>("/dashboard/invoices", {
      params: { project_id: projectId },
    });
    return data;
  },
  async calculations(projectId: ID): Promise<DashboardCalculation[]> {
    const { data } = await api.get<DashboardCalculation[]>(
      "/dashboard/calculations",
      { params: { project_id: projectId } }
    );
    return data;
  },
  async autoCalculate(projectId: ID): Promise<AutoCalculateResponse> {
    const { data } = await api.post<AutoCalculateResponse>(
      "/dashboard/auto-calculate",
      null,
      { params: { project_id: projectId } }
    );
    return data;
  },
  async calculate(input: CalculateInput): Promise<void> {
    const params: Record<string, string | number> = {
      project_id: input.project_id,
      period_start: input.period_start,
      period_end: input.period_end,
    };
    if (input.material_class_id) {
      params.material_class_id = input.material_class_id;
    }
    await api.post("/dashboard/calculate", null, { params });
  },
};
