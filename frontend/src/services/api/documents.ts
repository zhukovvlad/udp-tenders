import api from "@/lib/api";

export interface DocumentSummary {
  id: number;
  project_id: number;
  filename: string;
  doc_type: string;
  status: string;
  uploaded_at: string | null;
  invoice_count: number;
  has_issues: boolean;
  ai_confidence: number | null;
}

export const documentsApi = {
  async list(projectId?: number): Promise<DocumentSummary[]> {
    const { data } = await api.get<DocumentSummary[]>("/documents", {
      params: projectId != null ? { project_id: projectId } : undefined,
    });
    return data;
  },
};
