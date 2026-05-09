import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Download } from "lucide-react";
import api from "@/lib/api";

interface Project {
  id: number;
  name: string;
}

interface MaterialClass {
  id: number;
  name: string;
}

export default function Reports() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [materialClasses, setMaterialClasses] = useState<MaterialClass[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [selectedClass, setSelectedClass] = useState<string>("");
  const [periodStart, setPeriodStart] = useState<string>("");
  const [periodEnd, setPeriodEnd] = useState<string>("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.get("/projects").then((res) => setProjects(res.data));
    api.get("/material-classes").then((res) => setMaterialClasses(res.data));
  }, []);

  const handleDownload = async () => {
    if (!selectedProject) return;
    setDownloading(true);
    try {
      const params: Record<string, string> = { project_id: selectedProject };
      if (periodStart) params.period_start = periodStart;
      if (periodEnd) params.period_end = periodEnd;
      if (selectedClass) params.material_class_id = selectedClass;

      const res = await api.get("/export/excel", { params, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "report.xlsx");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      // handle error
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card>
      <CardHeader><CardTitle>Выгрузка отчёта в Excel</CardTitle></CardHeader>
      <CardContent>
        <div className="flex gap-4 items-end flex-wrap">
          <div className="space-y-2">
            <Label>Объект *</Label>
            <Select value={selectedProject} onValueChange={setSelectedProject}>
              <SelectTrigger className="w-[280px]">
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
            <Label htmlFor="rep-start">Период с</Label>
            <Input
              id="rep-start"
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-[160px]"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="rep-end">Период по</Label>
            <Input
              id="rep-end"
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="w-[160px]"
            />
          </div>

          <div className="space-y-2">
            <Label>Класс материала</Label>
            <Select value={selectedClass} onValueChange={setSelectedClass}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="Все классы" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Все классы</SelectItem>
                {materialClasses.map((mc) => (
                  <SelectItem key={mc.id} value={String(mc.id)}>{mc.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button onClick={handleDownload} disabled={!selectedProject || downloading}>
            <Download className="h-4 w-4 mr-2" />
            {downloading ? "Генерация..." : "Скачать Excel"}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mt-4">
          Отчёт содержит сводную таблицу цен по объекту с разбивкой по классам материалов.
        </p>
      </CardContent>
    </Card>
  );
}
