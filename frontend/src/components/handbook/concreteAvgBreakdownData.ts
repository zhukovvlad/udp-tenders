import type { ConcreteSfData } from "./ConcreteAvgBreakdown";

export const DEMO_SF: ConcreteSfData = {
  invoiceLabel: "СФ ЦБ-390 · Термобетон",
  baseLines: [
    { cls: "В40", name: "Бетон БСТ В40 П4 F200", qty: 14, sumWithVat: 122640 },
    { cls: "В30", name: "Бетон БСТ В30", qty: 107, sumWithVat: 732360 },
  ],
  deliveryWithVat: 145200,
  additiveWithVat: 0,
  otherLines: [{ name: "Цементное молочко", qty: 1, sumWithVat: 8130 }],
};
