"use client";

import { FolderKanbanIcon, MessageSquarePlus } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/core/i18n/hooks";
import { useProjects } from "@/core/projects";
import { cn } from "@/lib/utils";

/**
 * 长伴咨询 workbench project list.
 *
 * The project records are upstream's (SQL-backed — see
 * `backend/app/gateway/routers/projects.py`). This page is only the
 * workbench entry point: per-project detail (the consultation brief in
 * `instructions`, the document shelf of materials and deliverables, and the
 * attached conversations) lives in `/workspace/projects/[id]`, which upstream
 * owns. Starting a conversation from a project attaches it to that project.
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
            <div
              key={project.id}
              className="bg-card flex flex-col gap-2 rounded-lg border p-4"
            >
              <div className="flex min-w-0 items-start justify-between gap-2">
                <Link
                  href={`/workspace/projects/${project.id}`}
                  className="flex min-w-0 items-center gap-2 hover:underline"
                >
                  <FolderKanbanIcon className="h-4 w-4 shrink-0" />
                  <span className="truncate font-medium">{project.name}</span>
                </Link>
                {project.status === "archived" ? (
                  <Badge variant="secondary">{t.projects.archived}</Badge>
                ) : null}
              </div>

              {project.instructions ? (
                <p className="cb-muted line-clamp-3 text-sm">
                  {project.instructions}
                </p>
              ) : null}

              <div className="mt-auto flex items-center gap-2 pt-1">
                <Link
                  href={`/workspace/projects/${project.id}`}
                  className="text-muted-foreground hover:text-foreground text-xs underline-offset-4 hover:underline"
                >
                  {t.projects.settings}
                </Link>
                {project.status !== "archived" ? (
                  <Link
                    href={`/workspace/chats/new?project=${encodeURIComponent(project.id)}`}
                    className={cn(
                      "text-muted-foreground hover:text-foreground ml-auto",
                      "inline-flex items-center gap-1 text-xs underline-offset-4 hover:underline",
                    )}
                  >
                    <MessageSquarePlus className="h-3.5 w-3.5" />
                    {t.projects.newChat}
                  </Link>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
