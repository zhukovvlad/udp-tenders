import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { Upload as UploadIcon, Trash2, FileEdit, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import api from "@/lib/api";

interface Project {
  id: number;
  name: string;
}

interface UploadResult {
  filename: string;
  status: string;
  error?: string;
}

interface Document {
  id: number;
  project_id: number;
  filename: string;
  doc_type: string;
  status: string;
  uploaded_at: string;
  invoice_count: number;
  has_issues: boolean;
  ai_confidence: number | null;
}

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  processed: "default",
  processing: "secondary",
  error: "destructive",
  pending: "outline",
  queue: "outline",
};

const statusLabel: Record<string, string> = {
  processed: "Обработан",
  processing: "Обрабатывается",
  error: "Ошибка",
  pending: "Ожидание",
  queue: "В очереди",
};

export default function UploadPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    api.get("/projects").then((res) => setProjects(res.data));
  }, []);

  const loadDocuments = (projectId: string) => {
    if (!projectId) return;
    api.get("/invoices/documents", { params: { project_id: projectId } })
      .then((res) => setDocuments(res.data));
  };

  const handleProjectChange = (val: string) => {
    setSelectedProject(val);
    setResults([]);
    loadDocuments(val);
  };

  const uploadFile = async (file: File) => {
    if (!selectedProject) return;
    setResults((prev) => [...prev, { filename: file.name, status: "queue" }]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      await api.post("/invoices/upload", formData, {
        params: { project_id: selectedProject },
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResults((prev) =>
        prev.map((r) => r.filename === file.name ? { ...r, status: "processed" } : r)
      );
      loadDocuments(selectedProject);
    } catch {
      setResults((prev) =>
        prev.map((r) => r.filename === file.name ? { ...r, status: "error", error: "Ошибка загрузки" } : r)
      );
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Удалить документ и все связанные данные?")) return;
    await api.delete(`/invoices/documents/${id}`);
    loadDocuments(selectedProject);
  };

  const [retrying, setRetrying] = useState<number | null>(null);
  const handleReparse = async (id: number) => {
    setRetrying(id);
    try {
      await api.post(`/invoices/documents/${id}/reparse`);
      loadDocuments(selectedProject);
    } finally {
      setRetrying(null);
    }
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (!selectedProject) return;
      const files = Array.from(e.dataTransfer.files).filter((f) => f.name.endsWith(".pdf"));
      files.forEach(uploadFile);
    },
    [selectedProject]
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach(uploadFile);
    e.target.value = "";
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Объект *</Label>
        <Select value={selectedProject} onValueChange={handleProjectChange}>
          <SelectTrigger className="w-[320px]">
            <SelectValue placeholder="Выберите объект для загрузки" />
          </SelectTrigger>
          <SelectContent>
            {projects.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          !selectedProject
            ? "border-muted-foreground/15 opacity-50 cursor-not-allowed"
            : dragOver
            ? "border-primary bg-primary/5 cursor-pointer"
            : "border-muted-foreground/25 hover:border-primary/50 cursor-pointer"
        }`}
        onDragOver={(e) => { e.preventDefault(); if (selectedProject) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => { if (selectedProject) document.getElementById("file-input")?.click(); }}
      >
        <UploadIcon className="h-10 w-10 mx-auto mb-4 text-muted-foreground" />
        {selectedProject ? (
          <>
            <p className="text-lg font-medium">Перетащите PDF-файлы УПД сюда</p>
            <p className="text-sm text-muted-foreground mt-1">или нажмите для выбора файлов</p>
          </>
        ) : (
          <p className="text-lg font-medium text-muted-foreground">Сначала выберите объект</p>
        )}
        <input
          id="file-input"
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          onChange={handleFileSelect}
        />
      </div>

      {results.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Результаты загрузки</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {results.map((item, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div>
                    <p className="font-medium">{item.filename}</p>
                    {item.error && <p className="text-sm text-destructive">{item.error}</p>}
                  </div>
                  <Badge variant={statusVariant[item.status] ?? "outline"}>
                    {statusLabel[item.status] ?? item.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {selectedProject && (
        <Card>
          <CardHeader><CardTitle>Документы объекта</CardTitle></CardHeader>
          <CardContent>
            {documents.length === 0 ? (
              <p className="text-center text-muted-foreground py-6">Документы не загружены</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Файл</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>УПД в документе</TableHead>
                    <TableHead>ИИ</TableHead>
                    <TableHead>Загружен</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {documents.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell className="font-medium">{doc.filename}</TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          <Badge variant={statusVariant[doc.status] ?? "outline"}>
                            {statusLabel[doc.status] ?? doc.status}
                          </Badge>
                          {doc.has_issues && (
                            <Badge variant="secondary" className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                              Требует проверки
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{doc.invoice_count}</TableCell>
                      <TableCell>
                        {doc.ai_confidence != null ? (
                          <Badge
                            variant="outline"
                            className={
                              doc.ai_confidence >= 0.85
                                ? "bg-green-50 text-green-700"
                                : doc.ai_confidence >= 0.7
                                ? "bg-amber-50 text-amber-700"
                                : "bg-red-50 text-red-700"
                            }
                          >
                            {Math.round(doc.ai_confidence * 100)}%
                          </Badge>
                        ) : "—"}
                      </TableCell>
                      <TableCell>{new Date(doc.uploaded_at).toLocaleString("ru-RU")}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {doc.status === "error" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleReparse(doc.id)}
                              disabled={retrying === doc.id}
                              title="Повторить парсинг"
                            >
                              <RefreshCw className={`h-4 w-4 ${retrying === doc.id ? "animate-spin" : ""}`} />
                            </Button>
                          )}
                          <Button variant="ghost" size="icon" asChild title="Редактировать">
                            <Link to={`/documents/${doc.id}`}>
                              <FileEdit className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => handleDelete(doc.id)} title="Удалить">
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
