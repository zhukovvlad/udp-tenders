import { useMemo, useState } from "react";
import { Plus, Search, Building2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { Button } from "@/components/ui-domain/Button";
import { PageHeader } from "@/components/ui-domain/PageHeader";
import { EmptyState } from "@/components/ui-domain/EmptyState";
import { Skeleton } from "@/components/ui-domain/Skeleton";
import { ProjectCard } from "@/components/projects/ProjectCard";

import { useProjects, useCreateProject } from "@/services/queries";

export default function Projects() {
  const projectsQ = useProjects();
  const create = useCreateProject();

  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [contract, setContract] = useState("");

  const filtered = useMemo(() => {
    const list = projectsQ.data ?? [];
    if (!search.trim()) return list;
    const q = search.trim().toLowerCase();
    return list.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.contract_number ?? "").toLowerCase().includes(q)
    );
  }, [projectsQ.data, search]);

  const submit = () => {
    if (!name.trim()) return;
    create.mutate(
      { name: name.trim(), contract_number: contract.trim() || null },
      {
        onSuccess: () => {
          setOpen(false);
          setName("");
          setContract("");
        },
      }
    );
  };

  return (
    <div className="container-page py-8">
      <PageHeader
        serif
        title="Объекты"
        subtitle={
          (projectsQ.data ?? []).length > 0
            ? `${(projectsQ.data ?? []).length} объектов в портфеле`
            : "Здесь появится ваш портфель объектов"
        }
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger render={<Button leftIcon={<Plus size={14} />}>Новый объект</Button>} />
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Создать объект</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
                    Название *
                  </Label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="ЖК «Северный», корпус 1"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-2xs uppercase tracking-wider text-fg-tertiary">
                    Номер договора
                  </Label>
                  <Input
                    value={contract}
                    onChange={(e) => setContract(e.target.value)}
                    placeholder="Опционально"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="ghost" onClick={() => setOpen(false)}>
                  Отмена
                </Button>
                <Button
                  onClick={submit}
                  loading={create.isPending}
                  disabled={!name.trim()}
                >
                  Создать
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <div className="mt-6 relative w-full max-w-md">
        <Search
          size={14}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-tertiary"
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по названию или договору"
          className="w-full rounded-md border border-border-subtle bg-surface py-2 pl-9 pr-3 text-sm text-fg placeholder:text-fg-tertiary focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
      </div>

      <div className="mt-6">
        {projectsQ.isLoading ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[120px]" />
            ))}
          </div>
        ) : (projectsQ.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Building2 size={20} />}
            title="Создайте первый объект"
            description="Объект — это контейнер для договоров и счетов-фактур. С него начинается работа в УПД Трекере."
            action={
              <Button leftIcon={<Plus size={14} />} onClick={() => setOpen(true)}>
                Новый объект
              </Button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="Ничего не найдено"
            description="Попробуйте изменить запрос."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
