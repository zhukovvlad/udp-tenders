import api from "@/lib/api";
import type { ID, ISODate } from "@/types/common";

export interface ExcelExportInput {
  project_id: ID;
  period_start?: ISODate;
  period_end?: ISODate;
}

export const reportsApi = {
  async excelBlob(input: ExcelExportInput): Promise<Blob> {
    const { data } = await api.get<Blob>("/export/excel", {
      params: input,
      responseType: "blob",
    });
    return data;
  },
};
