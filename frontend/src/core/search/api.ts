import { getBackendBaseURL } from "@/core/config";

export interface SearchHit {
  kind: "project" | "output" | "material" | "method";
  title: string;
  snippet: string;
  project_id: string;
  target_id: string;
}

export async function searchWorkbench(query: string): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q: query });
  const res = await fetch(`${getBackendBaseURL()}/api/search?${params}`);
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
  const data = (await res.json()) as { results: SearchHit[] };
  return data.results;
}

export function hrefOfHit(hit: SearchHit): string {
  if (hit.kind === "method") return "/workspace/methods";
  return `/workspace/projects/${hit.project_id}`;
}
