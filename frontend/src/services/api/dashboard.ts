import api from "@/lib/api";
import type {
  DashboardCalculation,
  DashboardInvoices,
  DashboardSummary,
  MonthlyBucketRaw,
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
  async calculations(
    projectId: ID,
    periodStart?: string,
    periodEnd?: string,
  ): Promise<DashboardCalculation[]> {
    const params: Record<string, string | number> = { project_id: projectId };
    if (periodStart) params.period_start = periodStart;
    if (periodEnd) params.period_end = periodEnd;
    const { data } = await api.get<DashboardCalculation[]>("/dashboard/calculations", { params });
    return data;
  },
  async calculationsAll(): Promise<DashboardCalculation[]> {
    const { data } = await api.get<DashboardCalculation[]>("/dashboard/calculations");
    return data;
  },
  async monthlySummary(projectId: ID): Promise<MonthlyBucketRaw[]> {
    const { data } = await api.get<MonthlyBucketRaw[]>("/dashboard/monthly-summary", {
      params: { project_id: projectId },
    });
    return data;
  },
};
