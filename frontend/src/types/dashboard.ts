import type { ID, ISODate } from "./common";
import type { DashboardInvoiceRow } from "./invoice";

export interface DashboardSummary {
  doc_count: number;
  invoice_count: number;
  total_amount: number;
  total_qty: number;
  first_invoice_date: ISODate | null;
  last_invoice_date: ISODate | null;
  full_deviation_amount: number | null;
}

export interface DashboardCalculation {
  material_class_name: string;
  period_start: ISODate;
  period_end: ISODate;
  avg_price: number;
  reference_price: number | null;
  deviation_pct: number | null;
  deviation_amount: number | null;
  material_total: number | null;
  delivery_total: number | null;
  total_qty: number;
  invoice_count: number;
}

export interface AutoCalculateResponse {
  period_start: ISODate | null;
  period_end: ISODate | null;
}

export interface CalculateInput {
  project_id: ID;
  material_class_id?: ID;
  period_start: ISODate;
  period_end: ISODate;
}

export type DashboardInvoices = DashboardInvoiceRow[];
