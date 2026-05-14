import type { ID, ISODate, ISODateTime } from "./common";

export interface MaterialClassRef {
  id: ID;
  name: string;
}

export interface InvoiceItem {
  id?: ID;
  raw_name: string;
  item_type: "material" | "delivery" | "other";
  /**
   * Класс материала, привязанный к позиции. Бэкенд сериализует как {id, name} либо null.
   */
  material_class: MaterialClassRef | null;
  material_class_id?: ID | null;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
  vat_amount?: number | null;
}

export interface InvoiceRow {
  id: ID;
  document_id: ID;
  number: string;
  date: ISODate;
  supplier_name: string | null;
  supplier_inn?: string | null;
  vat_rate: number;
  ai_confidence: number | null;
  has_issues: boolean;
  verified: boolean;
  verified_at: ISODateTime | null;
  items: InvoiceItem[];
}

export interface DocumentSummary {
  id: ID;
  project_id: ID;
  filename: string;
  doc_type: string;
  status: string;
  uploaded_at: ISODateTime;
  invoice_count: number;
  has_issues: boolean;
  ai_confidence: number | null;
}

export interface DocumentDetail extends DocumentSummary {
  invoices: InvoiceRow[];
}

export interface InvoiceUpdateInput {
  number?: string;
  date?: ISODate;
  supplier_name?: string | null;
  supplier_inn?: string | null;
  vat_rate?: number;
  items?: InvoiceItem[];
}
