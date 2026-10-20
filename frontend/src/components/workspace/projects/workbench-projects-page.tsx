"use client";

import Link from "next/link";

import { useI18n } from "@/core/i18n/hooks";
import { useProjects } from "@/core/projects";
import { cn } from "@/lib/utils";

/**
 * 长伴咨询 workbench project list.
 *
 * The project records themselves are upstream's (SQL-backed, see
 * `backend/app/gateway/routers/projects.py`); this page only gives the
 * workbench home a place to list them. Per-project detail lives in
 * `/workspace/projects/[id]`, which upstream owns.
 */
export function WorkbenchProjectsPage() {
  const { t } = useI18n();
  const { data: projects = [], isLoading } = useProjects();

  return (
    <div className="cb-page flex size-full flex-col overflow-auto">
      <div className="cb-page-head">
        <h1>{t.projects.title}</h1>
      </div>

      {isLoading ? (
        <p className="cb-muted text-sm">{t.common.loading}</p>
      ) : projects.length === 0 ? (
        <p className="cb-muted text-sm">{t.projects.empty}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/workspace/projects/${project.id}`}
              className={cn(
                "bg-card flex flex-col gap-1 rounded-lg border p-4 transition-colors",
                "hover:bg-accent/40",
              )}
            >
              <span className="truncate font-medium">{project.name}</span>
              {project.instructions ? (
                <span className="cb-muted line-clamp-2 text-sm">
                  {project.instructions}
                </span>
              ) : null}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
