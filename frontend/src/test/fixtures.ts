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
