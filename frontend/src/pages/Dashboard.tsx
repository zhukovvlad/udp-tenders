import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { FileEdit, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import api from "@/lib/api";

interface Project {
  id: number;
  name: string;
}

interface MaterialClass {
  id: number;
  name: string;
}

interface Summary {
  doc_count: number;
  invoice_count: number;
  total_amount: number;
  total_qty: number;
}

interface InvoiceItem {
  raw_name: string;
  item_type: string;
  material_class: string | null;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
}

interface InvoiceRow {
  id: number;
  document_id: number;
  number: string;
  date: string;
  supplier_name: string;
  vat_rate: number;
  ai_confidence: number | null;
  has_issues: boolean;
  items: InvoiceItem[];
}

interface Calculation {
  material_class_name: string;
  period_start: string;
  period_end: string;
  avg_price: number;
  reference_price: number;
  deviation_pct: number;
  deviation_amount: number;
  total_qty: number;
  invoice_count: number;
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [materialClasses, setMaterialClasses] = useState<MaterialClass[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [selectedClass, setSelectedClass] = useState<string>("");
  const [periodStart, setPeriodStart] = useState<string>("");
  const [periodEnd, setPeriodEnd] = useState<string>("");

  const [summary, setSummary] = useState<Summary | null>(null);
  const [invoices, setInvoices] = useState<InvoiceRow[]>([]);
  const [calculations, setCalculations] = useState<Calculation[]>([]);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    api.get("/projects").then((res) => setProjects(res.data));
    api.get("/material-classes").then((res) => setMaterialClasses(res.data));
  }, []);

  const loadProjectData = (projectId: string) => {
    if (!projectId) return;
    api.get("/dashboard/summary", { params: { project_id: projectId } })
      .then((res) => setSummary(res.data));
    api.get("/dashboard/invoices", { params: { project_id: projectId } })
      .then((res) => setInvoices(res.data));
    api.get("/dashboard/calculations", { params: { project_id: projectId } })
      .then((res) => setCalculations(res.data));
  };

  const handleProjectChange = async (val: string) => {
    setSelectedProject(val);
    if (!val) return;
    // Автоматически считаем по всему диапазону дат СФ проекта
    try {
      const res = await api.post("/dashboard/auto-calculate", null, {
        params: { project_id: val },
      });
      if (res.data.period_start) setPeriodStart(res.data.period_start);
      if (res.data.period_end) setPeriodEnd(res.data.period_end);
    } catch {
      // если расчёт не получился — всё равно показать что есть
    }
    loadProjectData(val);
  };

  const handleCalculate = async () => {
    if (!selectedProject || !periodStart || !periodEnd) return;
    setCalculating(true);
    try {
      const params: Record<string, string> = {
        project_id: selectedProject,
        period_start: periodStart,
        period_end: periodEnd,
      };
      if (selectedClass) params.material_class_id = selectedClass;
      await api.post("/dashboard/calculate", null, { params });
      loadProjectData(selectedProject);
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Фильтры */}
      <Card>
        <CardHeader><CardTitle>Аналитика</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-4 flex-wrap items-end">
            <div className="space-y-1">
              <Label>Объект *</Label>
              <Select value={selectedProject} onValueChange={(v) => handleProjectChange(v ?? "")}>
                <SelectTrigger className="w-[260px]">
                  <SelectValue placeholder="Выберите объект" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Класс материала</Label>
              <Select value={selectedClass} onValueChange={(v) => setSelectedClass(v ?? "")}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Выберите класс" />
                </SelectTrigger>
                <SelectContent>
                  {materialClasses.map((mc) => (
                    <SelectItem key={mc.id} value={String(mc.id)}>{mc.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Период с</Label>
              <Input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} className="w-[160px]" />
            </div>
            <div className="space-y-1">
              <Label>Период по</Label>
              <Input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} className="w-[160px]" />
            </div>
            <Button
              onClick={handleCalculate}
              disabled={!selectedProject || !selectedClass || !periodStart || !periodEnd || calculating}
            >
              {calculating ? "Расчёт..." : "Рассчитать"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Сводка */}
      {summary && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Документов</p>
              <p className="text-2xl font-bold">{summary.doc_count}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Счетов-фактур</p>
              <p className="text-2xl font-bold">{summary.invoice_count}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Объём (м3)</p>
              <p className="text-2xl font-bold">{summary.total_qty.toLocaleString("ru-RU")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Сумма (₽)</p>
              <p className="text-2xl font-bold">{summary.total_amount.toLocaleString("ru-RU")}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Расчёты отклонений */}
      {calculations.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Расчёты отклонений</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Класс</TableHead>
                  <TableHead>Период</TableHead>
                  <TableHead>Ср. цена, ₽</TableHead>
                  <TableHead>Эталон, ₽</TableHead>
                  <TableHead>Откл., %</TableHead>
                  <TableHead>Откл., ₽</TableHead>
                  <TableHead>Объём</TableHead>
                  <TableHead>СФ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {calculations.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{row.material_class_name}</TableCell>
                    <TableCell>{row.period_start} — {row.period_end}</TableCell>
                    <TableCell>{Number(row.avg_price).toLocaleString("ru-RU")}</TableCell>
                    <TableCell>{row.reference_price ? Number(row.reference_price).toLocaleString("ru-RU") : "—"}</TableCell>
                    <TableCell className={row.deviation_pct > 0 ? "text-destructive font-medium" : row.deviation_pct < 0 ? "text-green-600 font-medium" : ""}>
                      {row.deviation_pct != null ? `${row.deviation_pct > 0 ? "+" : ""}${row.deviation_pct.toFixed(1)}%` : "—"}
                    </TableCell>
                    <TableCell className={row.deviation_amount > 0 ? "text-destructive" : row.deviation_amount < 0 ? "text-green-600" : ""}>
                      {row.deviation_amount != null ? `${row.deviation_amount > 0 ? "+" : ""}${Number(row.deviation_amount).toLocaleString("ru-RU")}` : "—"}
                    </TableCell>
                    <TableCell>{row.total_qty}</TableCell>
                    <TableCell>{row.invoice_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Список СФ */}
      {invoices.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Счета-фактуры ({invoices.length})</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Номер</TableHead>
                  <TableHead>Дата</TableHead>
                  <TableHead>Поставщик</TableHead>
                  <TableHead>Позиции</TableHead>
                  <TableHead>Сумма, ₽</TableHead>
                  <TableHead>ИИ</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow
                    key={inv.id}
                    className={`hover:bg-muted/50 ${inv.has_issues ? "bg-amber-50" : ""}`}
                  >
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-1.5">
                        {inv.has_issues && (
                          <AlertTriangle className="h-4 w-4 text-amber-600" aria-label="Требует проверки" />
                        )}
                        {inv.number}
                      </div>
                    </TableCell>
                    <TableCell>{inv.date}</TableCell>
                    <TableCell>{inv.supplier_name || "—"}</TableCell>
                    <TableCell>
                      {inv.items.map((item, i) => (
                        <div key={i} className="text-sm">
                          <Badge variant="outline" className="mr-1 text-xs">
                            {item.item_type === "material" ? item.material_class || "?" : item.item_type === "delivery" ? "доставка" : "прочее"}
                          </Badge>
                          {item.raw_name?.slice(0, 40)}{item.raw_name && item.raw_name.length > 40 ? "..." : ""} — {item.quantity} {item.unit}
                        </div>
                      ))}
                    </TableCell>
                    <TableCell>{inv.items.reduce((s, i) => s + i.amount, 0).toLocaleString("ru-RU")}</TableCell>
                    <TableCell>
                      {inv.ai_confidence != null ? (
                        <Badge
                          variant="outline"
                          className={
                            inv.ai_confidence >= 0.85
                              ? "bg-green-50 text-green-700"
                              : inv.ai_confidence >= 0.7
                              ? "bg-amber-50 text-amber-700"
                              : "bg-red-50 text-red-700"
                          }
                        >
                          {Math.round(inv.ai_confidence * 100)}%
                        </Badge>
                      ) : "—"}
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" asChild title="Редактировать">
                        <Link to={`/documents/${inv.document_id}`}>
                          <FileEdit className="h-4 w-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Пустое состояние */}
      {!selectedProject && (
        <p className="text-center text-muted-foreground py-12">Выберите объект для просмотра аналитики</p>
      )}
      {selectedProject && !summary?.invoice_count && (
        <p className="text-center text-muted-foreground py-12">Нет загруженных документов по этому объекту</p>
      )}
    </div>
  );
}
