export const sampleProject = {
  id: 1,
  name: "ЖК Радуга",
  contract_number: "Д-001",
  doc_count: 0,
};

export const sampleMaterialClass = {
  id: 1,
  name: "В25",
  material_type: "concrete",
};

export const sampleDocument = {
  id: 10,
  project_id: 1,
  filename: "doc.pdf",
  doc_type: "invoice",
  status: "parsed",
  uploaded_at: "2026-04-15T10:00:00",
  invoice_count: 1,
  has_issues: false,
  ai_confidence: 0.92,
  invoices: [
    {
      id: 100,
      document_id: 10,
      number: "СФ-101",
      date: "2026-04-15",
      supplier_name: "ООО Поставщик",
      supplier_inn: "0000000000",
      vat_rate: 20,
      ai_confidence: 0.92,
      has_issues: false,
      verified: false,
      verified_at: null,
      items: [
        {
          id: 1000,
          raw_name: "Бетон В25",
          item_type: "material",
          material_class: { id: 1, name: "В25" },
          material_class_id: 1,
          quantity: 7.0,
          unit: "м3",
          unit_price: 8000.0,
          amount: 56000.0,
          vat_amount: 9333.33,
        },
      ],
    },
  ],
};

export const sampleDashboardSummary = {
  doc_count: 3,
  invoice_count: 5,
  total_amount: 250000,
  total_qty: 31.5,
  first_invoice_date: "2026-01-01",
  last_invoice_date: "2026-04-15",
  full_deviation_amount: null,
};

export const sampleReferencePrice = {
  id: 1,
  project_id: 1,
  project_name: "ЖК Радуга",
  material_class_id: 1,
  material_class_name: "В25",
  price: 6010,
  period_start: "2025-01-01",
  period_end: "2026-12-31",
  source: "Договорённость",
};

const _baseItem = {
  raw_name: "Бетон В25",
  item_type: "material" as const,
  material_class: "В25",
  quantity: 5.0,
  unit: "м3",
  unit_price: 8000.0,
  amount: 40000.0,
};

export const sampleMonthlySummary = [
  { year: 2026, month: 1, total_amount: 120000, total_qty: 15.0, invoice_count: 2 },
  // февраль пропущен — фронт должен достроить его
  { year: 2026, month: 3, total_amount: 80000,  total_qty: 10.0, invoice_count: 1 },
];

export const sampleDashboardInvoices = [
  // Подтверждён
  {
    id: 201,
    document_id: 10,
    number: "СФ-CONFIRMED",
    date: "2026-03-01",
    supplier_name: "Поставщик А",
    supplier_inn: null,
    vat_rate: 20,
    ai_confidence: 0.92,
    has_issues: false,
    verified: true,
    verified_at: "2026-03-02T10:00:00",
    items: [_baseItem],
  },
  // Разобрать (низкая уверенность)
  {
    id: 202,
    document_id: 11,
    number: "СФ-REVIEW",
    date: "2026-03-05",
    supplier_name: "Поставщик Б",
    supplier_inn: null,
    vat_rate: 20,
    ai_confidence: 0.65,
    has_issues: false,
    verified: false,
    verified_at: null,
    items: [_baseItem],
  },
  // Ожидает
  {
    id: 203,
    document_id: 12,
    number: "СФ-PENDING",
    date: "2026-03-10",
    supplier_name: "Поставщик В",
    supplier_inn: null,
    vat_rate: 20,
    ai_confidence: 0.88,
    has_issues: false,
    verified: false,
    verified_at: null,
    items: [_baseItem],
  },
];
