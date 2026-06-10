export const sampleProject = {
  id: 1,
  name: "ЖК Радуга",
  contract_number: "Д-001",
  created_at: "2026-01-15T10:00:00",
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
          raw_unit: "м3",
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
  material_amount: 220000,
  delivery_amount: 30000,
  other_amount: 0,
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
  unit_id: 3,
  unit_symbol: "м³",
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
  raw_unit: "м3",
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

export const sampleSupplier = {
  id: 1,
  name: "ООО «ЭРКОН»",
  inn: "7723746396",
  created_at: "2025-01-01T00:00:00",
  invoice_count: 48,
  turnover: 18200000,
  project_count: 4,
  first_invoice_date: "2025-01-10",
  categories: ["В25", "В40"],
};

export const sampleSupplierProjectRows = [
  {
    project_id: 1,
    project_name: "ЖК Радуга",
    contract_number: "Д-001",
    invoice_count: 28,
    turnover: 11400000,
    volume_m3: 1842,
    deviation_pct: 2.8,
    deviation_amount: 318200,
  },
  {
    project_id: 2,
    project_name: "Бизнес-центр «Меридиан»",
    contract_number: "Д-002",
    invoice_count: 11,
    turnover: 4100000,
    volume_m3: 672,
    deviation_pct: 1.2,
    deviation_amount: 49700,
  },
];

export const sampleSupplierInvoices = [
  {
    id: 301,
    document_id: 10,
    number: "А-001",
    date: "2026-04-01",
    verified: false,
    verified_at: null,
    ai_confidence: 0.92,
    project_id: 1,
    project_name: "ЖК Радуга",
    amount: 450000,
  },
];

export const sampleUnits = [
  { id: 1, code: "TON", name: "Тонна", symbol: "т", dimension: "mass" as const, base_unit_id: null },
  { id: 2, code: "KG", name: "Килограмм", symbol: "кг", dimension: "mass" as const, base_unit_id: 1 },
  { id: 3, code: "M3", name: "Куб. метр", symbol: "м³", dimension: "volume" as const, base_unit_id: null },
  { id: 4, code: "M", name: "Метр", symbol: "м", dimension: "length" as const, base_unit_id: null },
  { id: 5, code: "PCS", name: "Штука", symbol: "шт", dimension: "count" as const, base_unit_id: null },
];

export const sampleMaterialTypes = [
  { id: 1, code: "concrete", name: "Бетон", default_unit: { id: 3, code: "M3", symbol: "м³" } },
  { id: 2, code: "rebar", name: "Арматура", default_unit: { id: 1, code: "TON", symbol: "т" } },
  { id: 3, code: "other", name: "Прочее", default_unit: null },
];
