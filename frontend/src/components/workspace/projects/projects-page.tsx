"use client";

import { Trash2Icon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/core/i18n/hooks";
import { useCreateProject, useDeleteProject, useProjects } from "@/core/projects/hooks";

export function ProjectsPage() {
  const { t } = useI18n();
  const { projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const [name, setName] = useState("");
  const [summary, setSummary] = useState("");

  async function handleAdd() {
    const trimmed = name.trim();
    if (!trimmed) {
      toast.error(t.projects.nameRequired);
      return;
    }
    try {
      await createProject.mutateAsync({ name: trimmed, summary: summary.trim() });
      setName("");
      setSummary("");
      toast.success(t.projects.added);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="cb-page flex size-full flex-col">
      <div className="cb-page-head">
        <h1>{t.projects.title}</h1>
        <p className="cb-kicker">{t.projects.description}</p>
      </div>
      <div className="cb-page-body">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void handleAdd();
          }}
        >
          <input
            className="cb-field"
            value={name}
            placeholder={t.projects.namePlaceholder}
            onChange={(event) => setName(event.target.value)}
          />
          <input
            className="cb-field"
            value={summary}
            placeholder={t.projects.summaryPlaceholder}
            onChange={(event) => setSummary(event.target.value)}
          />
          <button className="cb-action" type="submit" disabled={createProject.isPending}>
            {t.projects.add}
          </button>
        </form>
        {isLoading ? (
          <p className="cb-meta mt-4">{t.common.loading}</p>
        ) : projects.length === 0 ? (
          <p className="cb-meta mt-4">{t.projects.empty}</p>
        ) : (
          <ul className="cb-list mt-4">
            {projects.map((project) => (
              <li key={project.id} className="cb-row items-start">
                <Link
                  href={`/workspace/projects/${project.id}`}
                  className="min-w-0 flex-1"
                >
                  <div>{project.name}</div>
                  {project.summary ? (
                    <p className="cb-meta mt-0.5">{project.summary}</p>
                  ) : null}
                  {(project.thread_ids?.length ?? 0) > 0 ? (
                    <p className="cb-count mt-0.5">
                      {t.projects.chatCount.replace(
                        "{count}",
                        String(project.thread_ids.length),
                      )}
                    </p>
                  ) : null}
                </Link>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="text-destructive hover:text-destructive shrink-0"
                  aria-label={t.common.delete}
                  disabled={deleteProject.isPending}
                  onClick={() => {
                    void deleteProject
                      .mutateAsync(project.id)
                      .then(() => toast.success(t.projects.deleted))
                      .catch((err: unknown) => {
                        toast.error(err instanceof Error ? err.message : String(err));
                      });
                  }}
                >
                  <Trash2Icon className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
