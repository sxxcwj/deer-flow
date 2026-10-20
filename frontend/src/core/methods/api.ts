import { getBackendBaseURL } from "@/core/config";

import type { Method } from "./types";

export async function listMethods(): Promise<Method[]> {
  const res = await fetch(`${getBackendBaseURL()}/api/methods`);
  if (!res.ok) throw new Error(`Failed to load methods: ${res.statusText}`);
  const data = (await res.json()) as { methods: Method[] };
  return data.methods;
}

export async function createMethod(input: {
  title: string;
  body: string;
  file?: File;
}): Promise<Method> {
  const body = new FormData();
  body.append("title", input.title);
  body.append("body", input.body);
  if (input.file) body.append("file", input.file);
  const res = await fetch(`${getBackendBaseURL()}/api/methods`, {
    method: "POST",
    body,
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(err.detail ?? `Failed to save method: ${res.statusText}`);
  }
  return res.json() as Promise<Method>;
}

export async function deleteMethod(id: string): Promise<void> {
  const res = await fetch(`${getBackendBaseURL()}/api/methods/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete method: ${res.statusText}`);
}
