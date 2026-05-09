import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";
import api from "@/lib/api";

interface Project {
  id: number;
  name: string;
}

interface MaterialClass {
  id: number;
  name: string;
}

interface ReferencePrice {
  id: number;
  project_id: number;
  project_name: string;
  material_class_id: number;
  material_class_name: string;
  material_type: string;
  price: number;
  period_start: string;
  period_end: string;
  source: string;
}

const emptyForm = {
  project_id: "",
  material_class_id: "",
  price: "",
  period_start: "",
  period_end: "",
  source: "",
};

export default function ReferencePrices() {
  const [prices, setPrices] = useState<ReferencePrice[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [materialClasses, setMaterialClasses] = useState<MaterialClass[]>([]);
  const [filterProject, setFilterProject] = useState<string>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);

  const load = (projectFilter: string) => {
    const params: Record<string, string> = {};
    if (projectFilter && projectFilter !== "all") params.project_id = projectFilter;
    api.get("/reference-prices", { params }).then((res) => setPrices(res.data));
  };

  useEffect(() => {
    api.get("/projects").then((res) => setProjects(res.data));
    api.get("/material-classes").then((res) => setMaterialClasses(res.data));
    load("all");
  }, []);

  const handleFilterChange = (val: string) => {
    setFilterProject(val);
    load(val);
  };

  const openAdd = () => {
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.project_id || !form.material_class_id || !form.price || !form.period_start || !form.period_end) return;
    setLoading(true);
    try {
      await api.post("/reference-prices", {
        project_id: Number(form.project_id),
        material_class_id: Number(form.material_class_id),
        price: Number(form.price),
        period_start: form.period_start,
        period_end: form.period_end,
        source: form.source,
      });
      setDialogOpen(false);
      load(filterProject);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Удалить эталонную цену? Это действие необратимо.")) return;
    await api.delete(`/reference-prices/${id}`);
    load(filterProject);
  };

  const isFormValid =
    !!form.project_id &&
    !!form.material_class_id &&
    !!form.price &&
    !!form.period_start &&
    !!form.period_end;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Эталонные цены</h2>
        <Button onClick={openAdd}>
          <Plus className="h-4 w-4 mr-2" />
          Добавить эталон
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="space-y-1">
          <Label>Фильтр по объекту</Label>
          <Select value={filterProject} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-[280px]">
              <SelectValue placeholder="Все объекты" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все объекты</SelectItem>
              {projects.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Объект</TableHead>
                <TableHead>Класс материала</TableHead>
                <TableHead>Цена, &#8381;</TableHead>
                <TableHead>Период с</TableHead>
                <TableHead>Период по</TableHead>
                <TableHead>Источник</TableHead>
                <TableHead className="w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Эталонные цены не добавлены
                  </TableCell>
                </TableRow>
              ) : (
                prices.map((rp) => (
                  <TableRow key={rp.id}>
                    <TableCell className="font-medium">{rp.project_name}</TableCell>
                    <TableCell>{rp.material_class_name}</TableCell>
                    <TableCell>{Number(rp.price).toLocaleString("ru-RU")}</TableCell>
                    <TableCell>{rp.period_start}</TableCell>
                    <TableCell>{rp.period_end}</TableCell>
                    <TableCell>{rp.source || "—"}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(rp.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Добавить эталонную цену</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Объект *</Label>
              <Select
                value={form.project_id}
                onValueChange={(v) => setForm({ ...form, project_id: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите объект" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Класс материала *</Label>
              <Select
                value={form.material_class_id}
                onValueChange={(v) => setForm({ ...form, material_class_id: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите класс" />
                </SelectTrigger>
                <SelectContent>
                  {materialClasses.map((mc) => (
                    <SelectItem key={mc.id} value={String(mc.id)}>{mc.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rp-price">Цена, &#8381; *</Label>
              <Input
                id="rp-price"
                type="number"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                placeholder="0"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rp-start">Период с *</Label>
                <Input
                  id="rp-start"
                  type="date"
                  value={form.period_start}
                  onChange={(e) => setForm({ ...form, period_start: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rp-end">Период по *</Label>
                <Input
                  id="rp-end"
                  type="date"
                  value={form.period_end}
                  onChange={(e) => setForm({ ...form, period_end: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rp-source">Источник</Label>
              <Input
                id="rp-source"
                value={form.source}
                onChange={(e) => setForm({ ...form, source: e.target.value })}
                placeholder="Например: ФГИС ЦС"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Отмена</Button>
            <Button onClick={handleSave} disabled={loading || !isFormValid}>
              {loading ? "Сохранение..." : "Сохранить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
