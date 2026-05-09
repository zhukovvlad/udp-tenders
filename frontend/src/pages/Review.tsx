import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Plus, Trash2, Save } from "lucide-react";
import api from "@/lib/api";

interface MaterialClass {
  id: number;
  name: string;
  material_type: string;
}

interface InvoiceItem {
  id: number | null;
  raw_name: string;
  item_type: string;
  material_class: { id: number; name: string } | null;
  material_class_id?: number | null;
  quantity: number;
  unit: string | null;
  unit_price: number;
  amount: number;
  vat_amount: number | null;
}

interface Invoice {
  id: number;
  number: string;
  date: string;
  supplier_name: string | null;
  supplier_inn: string | null;
  vat_rate: number;
  items: InvoiceItem[];
}

interface DocumentData {
  id: number;
  filename: string;
  invoices: Invoice[];
}

const ITEM_TYPES = [
  { value: "material", label: "Материал" },
  { value: "delivery", label: "Доставка" },
  { value: "other", label: "Прочее" },
];

export default function Review() {
  const { id } = useParams();
  const [doc, setDoc] = useState<DocumentData | null>(null);
  const [classes, setClasses] = useState<MaterialClass[]>([]);
  const [saving, setSaving] = useState<number | null>(null);

  const loadDocument = () => {
    if (!id) return;
    api.get(`/invoices/documents/${id}`).then((res) => {
      const docData: DocumentData = res.data;
      // Маппим material_class в material_class_id для удобства редактирования
      docData.invoices.forEach((inv) => {
        inv.items.forEach((item) => {
          item.material_class_id = item.material_class?.id ?? null;
        });
      });
      setDoc(docData);
    });
  };

  useEffect(() => {
    loadDocument();
    api.get("/material-classes").then((res) => setClasses(res.data));
  }, [id]);

  const updateInvoice = (idx: number, patch: Partial<Invoice>) => {
    if (!doc) return;
    const next = { ...doc };
    next.invoices[idx] = { ...next.invoices[idx], ...patch };
    setDoc(next);
  };

  const updateItem = (invIdx: number, itemIdx: number, patch: Partial<InvoiceItem>) => {
    if (!doc) return;
    const next = { ...doc };
    next.invoices[invIdx].items[itemIdx] = { ...next.invoices[invIdx].items[itemIdx], ...patch };
    setDoc(next);
  };

  const addItem = (invIdx: number) => {
    if (!doc) return;
    const next = { ...doc };
    next.invoices[invIdx].items.push({
      id: null,
      raw_name: "",
      item_type: "material",
      material_class: null,
      material_class_id: null,
      quantity: 0,
      unit: "м3",
      unit_price: 0,
      amount: 0,
      vat_amount: null,
    });
    setDoc(next);
  };

  const removeItem = (invIdx: number, itemIdx: number) => {
    if (!doc) return;
    const next = { ...doc };
    next.invoices[invIdx].items.splice(itemIdx, 1);
    setDoc(next);
  };

  const saveInvoice = async (invIdx: number) => {
    if (!doc) return;
    const inv = doc.invoices[invIdx];
    setSaving(inv.id);
    try {
      await api.put(`/invoices/${inv.id}`, {
        number: inv.number,
        date: inv.date,
        supplier_name: inv.supplier_name,
        supplier_inn: inv.supplier_inn,
        vat_rate: inv.vat_rate,
        items: inv.items.map((item) => ({
          id: item.id,
          raw_name: item.raw_name,
          item_type: item.item_type,
          material_class_id: item.material_class_id,
          quantity: item.quantity,
          unit: item.unit,
          unit_price: item.unit_price,
          amount: item.amount,
          vat_amount: item.vat_amount,
        })),
      });
      loadDocument();
    } finally {
      setSaving(null);
    }
  };

  const deleteInvoice = async (invId: number) => {
    if (!confirm("Удалить эту счёт-фактуру?")) return;
    await api.delete(`/invoices/${invId}`);
    loadDocument();
  };

  if (!doc) return <div className="text-center py-20 text-muted-foreground">Загрузка...</div>;

  return (
    <div className="grid grid-cols-2 gap-6 h-[calc(100vh-8rem)]">
      <Card className="flex flex-col overflow-hidden">
        <CardHeader className="shrink-0">
          <CardTitle className="text-base">PDF: {doc.filename}</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 p-0">
          <iframe
            src={`/api/invoices/documents/${id}/pdf`}
            className="w-full h-full border-0"
            title="PDF просмотр"
          />
        </CardContent>
      </Card>

      <Card className="flex flex-col overflow-hidden">
        <CardHeader className="shrink-0">
          <CardTitle>Распознанные УПД ({doc.invoices.length})</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto space-y-8">
          {doc.invoices.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">УПД не найдены в документе</p>
          ) : (
            doc.invoices.map((inv, invIdx) => (
              <div key={inv.id} className="space-y-3">
                {invIdx > 0 && <Separator />}

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Номер</Label>
                    <Input
                      value={inv.number}
                      onChange={(e) => updateInvoice(invIdx, { number: e.target.value })}
                      className="h-8"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Дата</Label>
                    <Input
                      type="date"
                      value={inv.date}
                      onChange={(e) => updateInvoice(invIdx, { date: e.target.value })}
                      className="h-8"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Поставщик</Label>
                    <Input
                      value={inv.supplier_name || ""}
                      onChange={(e) => updateInvoice(invIdx, { supplier_name: e.target.value })}
                      className="h-8"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">ИНН</Label>
                    <Input
                      value={inv.supplier_inn || ""}
                      onChange={(e) => updateInvoice(invIdx, { supplier_inn: e.target.value })}
                      className="h-8"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">НДС, %</Label>
                    <Input
                      type="number"
                      value={inv.vat_rate}
                      onChange={(e) => updateInvoice(invIdx, { vat_rate: parseFloat(e.target.value) || 0 })}
                      className="h-8"
                    />
                  </div>
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-[180px]">Наименование</TableHead>
                      <TableHead>Тип</TableHead>
                      <TableHead>Класс</TableHead>
                      <TableHead>Кол-во</TableHead>
                      <TableHead>Ед.</TableHead>
                      <TableHead>Цена</TableHead>
                      <TableHead>Сумма</TableHead>
                      <TableHead className="w-8"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {inv.items.map((item, itemIdx) => {
                      const hasIssue =
                        (item.quantity || 0) <= 0 ||
                        !(item.raw_name || "").trim();
                      return (
                      <TableRow key={item.id ?? `new-${itemIdx}`} className={hasIssue ? "bg-amber-50" : ""}>
                        <TableCell>
                          <Input
                            value={item.raw_name}
                            onChange={(e) => updateItem(invIdx, itemIdx, { raw_name: e.target.value })}
                            className="h-8 text-xs"
                          />
                        </TableCell>
                        <TableCell>
                          <Select
                            value={item.item_type}
                            onValueChange={(v) => updateItem(invIdx, itemIdx, { item_type: v ?? "" })}
                          >
                            <SelectTrigger className="h-8 w-[110px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {ITEM_TYPES.map((t) => (
                                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Select
                            value={item.material_class_id ? String(item.material_class_id) : "none"}
                            onValueChange={(v) =>
                              updateItem(invIdx, itemIdx, {
                                material_class_id: v === "none" ? null : parseInt(v ?? "0"),
                              })
                            }
                          >
                            <SelectTrigger className="h-8 w-[90px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">—</SelectItem>
                              {classes.map((c) => (
                                <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            value={item.quantity}
                            onChange={(e) => updateItem(invIdx, itemIdx, { quantity: parseFloat(e.target.value) || 0 })}
                            className="h-8 w-[80px]"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={item.unit || ""}
                            onChange={(e) => updateItem(invIdx, itemIdx, { unit: e.target.value })}
                            className="h-8 w-[60px]"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            value={item.unit_price}
                            onChange={(e) => updateItem(invIdx, itemIdx, { unit_price: parseFloat(e.target.value) || 0 })}
                            className="h-8 w-[100px]"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            value={item.amount}
                            onChange={(e) => updateItem(invIdx, itemIdx, { amount: parseFloat(e.target.value) || 0 })}
                            className="h-8 w-[110px]"
                          />
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" onClick={() => removeItem(invIdx, itemIdx)}>
                            <Trash2 className="h-3 w-3 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>

                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => addItem(invIdx)}>
                    <Plus className="h-3 w-3 mr-1" /> Позиция
                  </Button>
                  <Button size="sm" onClick={() => saveInvoice(invIdx)} disabled={saving === inv.id}>
                    <Save className="h-3 w-3 mr-1" />
                    {saving === inv.id ? "Сохранение..." : "Сохранить"}
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => deleteInvoice(inv.id)}>
                    <Trash2 className="h-3 w-3 mr-1" /> Удалить СФ
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
