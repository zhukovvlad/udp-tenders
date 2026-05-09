import { Link } from "react-router-dom";
import { Building2 } from "lucide-react";
import { formatDate } from "@/lib/format";
import type { Project } from "@/types/project";

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Link
      to={`/projects/${project.id}`}
      className="group flex flex-col rounded-lg border border-border-subtle bg-surface px-5 py-4 transition-colors duration-150 hover:border-border-default hover:bg-surface-hover"
    >
      <div className="flex items-start gap-3">
        <div
          className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-accent-soft text-accent-text"
          aria-hidden
        >
          <Building2 size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-md font-medium text-fg">
            {project.name}
          </div>
          <div className="mt-0.5 truncate text-xs text-fg-secondary">
            {project.contract_number
              ? `Договор № ${project.contract_number}`
              : "Договор не указан"}
          </div>
        </div>
      </div>
      <div className="mt-4 border-t border-border-subtle pt-3 text-xs text-fg-tertiary">
        Создан {formatDate(project.created_at)}
      </div>
    </Link>
  );
}
