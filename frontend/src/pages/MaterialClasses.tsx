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

interface MaterialClass {
  id: number;
  name: string;
  material_type: string;
}

const materialTypeLabels: Record<string, string> = {
  concrete: "Бетон",
  rebar: "Арматура",
  other: "Прочее",
};

const emptyForm = { name: "", material_type: "" };

export default function MaterialClasses() {
  const [classes, setClasses] = useState<MaterialClass[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);

  const load = () => {
    api.get("/material-classes").then((res) => setClasses(res.data));
  };

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.material_type) return;
    setLoading(true);
    try {
      await api.post("/material-classes", form);
      setDialogOpen(false);
      load();
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Удалить класс материала? Это действие необратимо.")) return;
    await api.delete(`/material-classes/${id}`);
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Классы материалов</h2>
        <Button onClick={openAdd}>
          <Plus className="h-4 w-4 mr-2" />
          Добавить класс
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                <TableHead>Тип материала</TableHead>
                <TableHead className="w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {classes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-muted-foreground py-8">
                    Классы материалов не добавлены
                  </TableCell>
                </TableRow>
              ) : (
                classes.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell>{materialTypeLabels[c.material_type] ?? c.material_type}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(c.id)}>
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
            <DialogTitle>Добавить класс материала</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="mc-name">Название *</Label>
              <Input
                id="mc-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Например: Бетон М300"
              />
            </div>
            <div className="space-y-2">
              <Label>Тип материала *</Label>
              <Select
                value={form.material_type}
                onValueChange={(v) => setForm({ ...form, material_type: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите тип" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="concrete">Бетон</SelectItem>
                  <SelectItem value="rebar">Арматура</SelectItem>
                  <SelectItem value="other">Прочее</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Отмена</Button>
            <Button
              onClick={handleSave}
              disabled={loading || !form.name.trim() || !form.material_type}
            >
              {loading ? "Сохранение..." : "Сохранить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
