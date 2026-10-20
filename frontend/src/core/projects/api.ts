import { getBackendBaseURL } from "@/core/config";

import type { Project } from "./types";

export function projectMaterialURL(id: string, materialId: string): string {
  return `${getBackendBaseURL()}/api/projects/${id}/materials/${materialId}`;
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects`);
  if (!res.ok) throw new Error(`Failed to load projects: ${res.statusText}`);
  const data = (await res.json()) as { projects: Project[] };
  return data.projects;
}

export async function createProject(input: {
  name: string;
  summary: string;
}): Promise<Project> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to create project: ${res.statusText}`);
  }
  return res.json() as Promise<Project>;
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects/${id}`);
  if (res.status === 404) throw new Error("not_found");
  if (!res.ok) throw new Error(`Failed to load project: ${res.statusText}`);
  return res.json() as Promise<Project>;
}

export async function attachProjectThread(
  id: string,
  threadId: string,
): Promise<Project> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects/${id}/threads`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to attach conversation: ${res.statusText}`);
  }
  return res.json() as Promise<Project>;
}

export async function detachProjectThread(
  id: string,
  threadId: string,
): Promise<Project> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/projects/${id}/threads/${threadId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to detach conversation: ${res.statusText}`);
  return res.json() as Promise<Project>;
}

export async function addProjectOutput(
  id: string,
  input: { title: string; note: string },
): Promise<Project> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects/${id}/outputs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to add output: ${res.statusText}`);
  }
  return res.json() as Promise<Project>;
}

export async function deleteProjectOutput(
  id: string,
  outputId: string,
): Promise<Project> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/projects/${id}/outputs/${outputId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to delete output: ${res.statusText}`);
  return res.json() as Promise<Project>;
}

export async function saveChatFileAsMaterial(
  id: string,
  input: { threadId: string; path: string },
): Promise<Project> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects/${id}/materials/from-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: input.threadId, path: input.path }),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to save material: ${res.statusText}`);
  }
  return res.json() as Promise<Project>;
}

export async function uploadProjectMaterial(
  id: string,
  file: File,
): Promise<Project> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${getBackendBaseURL()}/api/projects/${id}/materials`, {
    method: "POST",
    body,
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to upload material: ${res.statusText}`);
  }
  return res.json() as Promise<Project>;
}

export async function deleteProjectMaterial(
  id: string,
  materialId: string,
): Promise<Project> {
  const res = await fetch(
    `${getBackendBaseURL()}/api/projects/${id}/materials/${materialId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Failed to delete material: ${res.statusText}`);
  return res.json() as Promise<Project>;
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${getBackendBaseURL()}/api/projects/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete project: ${res.statusText}`);
}
