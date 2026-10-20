"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { urlOfArtifact } from "@/core/artifacts/utils";
import { useI18n } from "@/core/i18n/hooks";
import { projectMaterialURL } from "@/core/projects/api";
import {
  useAddProjectOutput,
  useAttachProjectThread,
  useDeleteProjectMaterial,
  useDeleteProjectOutput,
  useDetachProjectThread,
  useProject,
  useSaveChatFileAsMaterial,
  useUploadProjectMaterial,
} from "@/core/projects/hooks";
import { useThreads } from "@/core/threads/hooks";
import type { AgentThread } from "@/core/threads/types";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";

export function ProjectDetail({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const projectQuery = useProject(projectId);
  const threadsQuery = useThreads({
    limit: 50,
    sortBy: "updated_at",
    sortOrder: "desc",
    select: ["thread_id", "updated_at", "values", "metadata"],
  });
  const attach = useAttachProjectThread();
  const detach = useDetachProjectThread();
  const addOutput = useAddProjectOutput();
  const deleteOutput = useDeleteProjectOutput();
  const uploadMaterial = useUploadProjectMaterial();
  const saveChatFile = useSaveChatFileAsMaterial();
  const deleteMaterial = useDeleteProjectMaterial();
  const materialInput = useRef<HTMLInputElement>(null);
  const [selectedId, setSelectedId] = useState("");
  const [outputTitle, setOutputTitle] = useState("");
  const [outputNote, setOutputNote] = useState("");
  const project = projectQuery.data;

  useEffect(() => {
    document.title = project
      ? `${project.name} - ${t.pages.appName}`
      : t.pages.appName;
  }, [project, t.pages.appName]);

  const threads = useMemo(() => threadsQuery.data ?? [], [threadsQuery.data]);
  const attached = useMemo(() => {
    const ids = new Set(project?.thread_ids ?? []);
    return threads
      .filter((thread) => ids.has(thread.thread_id))
      .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
  }, [project?.thread_ids, threads]);
  const attachedIds = useMemo(
    () => new Set(attached.map((thread) => thread.thread_id)),
    [attached],
  );
  const available = threads.filter((thread) => !attachedIds.has(thread.thread_id));
  const missingIds = (project?.thread_ids ?? []).filter((id) => !attachedIds.has(id));
  const continueThread = attached[0];
  const chatFiles = attached.flatMap((thread) =>
    (thread.values?.artifacts ?? []).map((filepath) => ({
      key: `${thread.thread_id}:${filepath}`,
      name: filepath.split("/").filter(Boolean).pop() ?? filepath,
      href: urlOfArtifact({ filepath, threadId: thread.thread_id }),
      threadId: thread.thread_id,
      filepath,
    })),
  );
  const outputs = project?.outputs ?? [];
  const materials = project?.materials ?? [];

  async function handleAddOutput() {
    const title = outputTitle.trim();
    if (!title) {
      toast.error(t.projects.outputTitleRequired);
      return;
    }
    try {
      await addOutput.mutateAsync({
        id: projectId,
        title,
        note: outputNote.trim(),
      });
      setOutputTitle("");
      setOutputNote("");
      toast.success(t.projects.outputAdded);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleAttach() {
    if (!selectedId) return;
    try {
      await attach.mutateAsync({ id: projectId, threadId: selectedId });
      setSelectedId("");
      toast.success(t.projects.attached);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  if (projectQuery.isLoading) {
    return <p className="cb-page cb-meta p-6">{t.common.loading}</p>;
  }

  if (!project) {
    return (
      <div className="cb-page p-6">
        <p className="text-sm">{t.projects.missing}</p>
        <Link href="/workspace/projects" className="cb-back mt-3 inline-block">
          {t.projects.back}
        </Link>
      </div>
    );
  }

  return (
    <div className="cb-page flex size-full flex-col">
      <div className="cb-page-head">
        <Link href="/workspace/projects" className="cb-back">
          {t.projects.back}
        </Link>
        <h1 className="mt-1">{project.name}</h1>
        {project.summary ? <p className="cb-kicker">{project.summary}</p> : null}
      </div>
      <div className="cb-page-body">
        <div className="flex flex-wrap gap-2">
          <Link className="cb-action" href={`/workspace/chats/new?project=${project.id}`}>
            {t.projects.newChat}
          </Link>
          {continueThread ? (
            <Button asChild variant="outline" className="h-8 rounded-[6px] text-[13px]">
              <Link href={pathOfThread(continueThread)}>{t.projects.continueChat}</Link>
            </Button>
          ) : null}
        </div>
        <h2 className="cb-section">{t.projects.chats}</h2>
        {attached.length === 0 && missingIds.length === 0 ? (
          <p className="cb-meta">{t.projects.chatsEmpty}</p>
        ) : (
          <ul className="cb-list">
            {attached.map((thread) => (
              <ThreadRow
                key={thread.thread_id}
                thread={thread}
                removeLabel={t.projects.removeChat}
                pending={detach.isPending}
                onRemove={() => {
                  void detach
                    .mutateAsync({ id: projectId, threadId: thread.thread_id })
                    .then(() => toast.success(t.projects.detached))
                    .catch((err: unknown) => {
                      toast.error(err instanceof Error ? err.message : String(err));
                    });
                }}
              />
            ))}
            {missingIds.map((threadId) => (
              <ThreadRow
                key={threadId}
                threadId={threadId}
                removeLabel={t.projects.removeChat}
                pending={detach.isPending}
                onRemove={() => {
                  void detach
                    .mutateAsync({ id: projectId, threadId })
                    .then(() => toast.success(t.projects.detached))
                    .catch((err: unknown) => {
                      toast.error(err instanceof Error ? err.message : String(err));
                    });
                }}
              />
            ))}
          </ul>
        )}
        {available.length > 0 ? (
          <form
            className="mt-4 flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void handleAttach();
            }}
          >
            <select
              className="cb-field"
              value={selectedId}
              onChange={(event) => setSelectedId(event.target.value)}
            >
              <option value="">{t.projects.attachPlaceholder}</option>
              {available.map((thread) => (
                <option key={thread.thread_id} value={thread.thread_id}>
                  {titleOfThread(thread)}
                </option>
              ))}
            </select>
            <Button
              type="submit"
              variant="outline"
              className="h-8 rounded-[6px] text-[13px]"
              disabled={!selectedId || attach.isPending}
            >
              {t.projects.attach}
            </Button>
          </form>
        ) : threads.length > 0 ? (
          <p className="cb-meta mt-4">{t.projects.noThreadsToAttach}</p>
        ) : null}
        <h2 className="cb-section">{t.projects.materials}</h2>
        {materials.length === 0 ? (
          <p className="cb-meta">{t.projects.materialsEmpty}</p>
        ) : (
          <ul className="cb-list">
            {materials.map((material) => (
              <li key={material.id} className="cb-row">
                <a
                  href={projectMaterialURL(project.id, material.id)}
                  className="min-w-0 flex-1 truncate"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {material.filename}
                </a>
                <span className="cb-count">{formatBytes(material.size)}</span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={deleteMaterial.isPending}
                  onClick={() => {
                    void deleteMaterial
                      .mutateAsync({ id: project.id, materialId: material.id })
                      .then(() => toast.success(t.projects.materialDeleted))
                      .catch((err: unknown) => {
                        toast.error(err instanceof Error ? err.message : String(err));
                      });
                  }}
                >
                  {t.common.delete}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <input
          ref={materialInput}
          type="file"
          hidden
          accept=".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (!file) return;
            void uploadMaterial
              .mutateAsync({ id: project.id, file })
              .then(() => toast.success(t.projects.materialAdded))
              .catch(() => toast.error(t.projects.materialRejected));
          }}
        />
        <Button
          type="button"
          variant="outline"
          className="mt-4 h-8 rounded-[6px] text-[13px]"
          disabled={uploadMaterial.isPending}
          onClick={() => materialInput.current?.click()}
        >
          {t.projects.uploadMaterial}
        </Button>
        <h2 className="cb-section">{t.projects.outputs}</h2>
        {outputs.length === 0 && chatFiles.length === 0 ? (
          <p className="cb-meta">{t.projects.outputsEmpty}</p>
        ) : (
          <ul className="cb-list">
            {outputs.map((output) => (
              <li
                key={output.id}
                className="cb-row items-start"
              >
                <div className="min-w-0">
                  <div className="text-sm">{output.title}</div>
                  {output.note ? <p className="cb-meta mt-0.5">{output.note}</p> : null}
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={deleteOutput.isPending}
                  onClick={() => {
                    void deleteOutput
                      .mutateAsync({ id: projectId, outputId: output.id })
                      .then(() => toast.success(t.projects.outputDeleted))
                      .catch((err: unknown) => {
                        toast.error(err instanceof Error ? err.message : String(err));
                      });
                  }}
                >
                  {t.common.delete}
                </Button>
              </li>
            ))}
            {chatFiles.map((file) => {
              const alreadyKept = materials.some((material) => material.filename === file.name);
              return (
                <li key={file.key} className="cb-row items-start">
                  <div className="min-w-0 flex-1">
                    <a
                      href={file.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm underline"
                    >
                      {file.name}
                    </a>
                    <p className="cb-meta mt-0.5">{t.projects.fromChat}</p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-8 rounded-[6px] text-[13px]"
                    disabled={alreadyKept || saveChatFile.isPending}
                    onClick={() => {
                      void saveChatFile
                        .mutateAsync({
                          id: project.id,
                          threadId: file.threadId,
                          path: file.filepath,
                        })
                        .then(() => toast.success(t.projects.materialKept))
                        .catch(() => toast.error(t.projects.materialRejected));
                    }}
                  >
                    {alreadyKept ? t.projects.materialKept : t.projects.keepMaterial}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        <form
          className="mt-4 flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void handleAddOutput();
          }}
        >
          <input
            className="cb-field"
            value={outputTitle}
            placeholder={t.projects.outputTitlePlaceholder}
            onChange={(event) => setOutputTitle(event.target.value)}
          />
          <input
            className="cb-field"
            value={outputNote}
            placeholder={t.projects.outputNotePlaceholder}
            onChange={(event) => setOutputNote(event.target.value)}
          />
          <Button
            type="submit"
            variant="outline"
            className="h-8 rounded-[6px] text-[13px]"
            disabled={addOutput.isPending}
          >
            {t.projects.addOutput}
          </Button>
        </form>
      </div>
    </div>
  );
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function ThreadRow({
  thread,
  threadId,
  removeLabel,
  pending,
  onRemove,
}: {
  thread?: AgentThread;
  threadId?: string;
  removeLabel: string;
  pending: boolean;
  onRemove: () => void;
}) {
  const id = thread?.thread_id ?? threadId ?? "";
  const href = thread ? pathOfThread(thread) : pathOfThread(id);
  const title = thread ? titleOfThread(thread) : id;
  return (
    <li className="cb-row">
      <Link href={href} className="min-w-0 flex-1 truncate">
        {title}
      </Link>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        disabled={pending}
        onClick={onRemove}
      >
        {removeLabel}
      </Button>
    </li>
  );
}
