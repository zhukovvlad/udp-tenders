import type { ISODate } from "./common";
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
  material_class_id: number;
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

export type DashboardInvoices = DashboardInvoiceRow[];

export interface MonthlyBucketRaw {
  year: number;
  month: number;
  total_amount: number;
  total_qty: number;
  invoice_count: number;
}
