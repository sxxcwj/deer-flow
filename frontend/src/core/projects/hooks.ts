import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addProjectOutput,
  attachProjectThread,
  createProject,
  deleteProject,
  deleteProjectMaterial,
  deleteProjectOutput,
  detachProjectThread,
  getProject,
  listProjects,
  saveChatFileAsMaterial,
  uploadProjectMaterial,
} from "./api";
import type { Project } from "./types";

export function useProjects() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });
  return { projects: data ?? [], isLoading, error };
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ["projects", id],
    queryFn: () => getProject(id),
    retry: false,
  });
}

function useProjectUpdate<T>(mutationFn: (input: T) => Promise<Project>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (project) => {
      queryClient.setQueryData(["projects", project.id], project);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useAttachProjectThread() {
  return useProjectUpdate(({ id, threadId }: { id: string; threadId: string }) =>
    attachProjectThread(id, threadId),
  );
}

export function useDetachProjectThread() {
  return useProjectUpdate(({ id, threadId }: { id: string; threadId: string }) =>
    detachProjectThread(id, threadId),
  );
}

export function useAddProjectOutput() {
  return useProjectUpdate(
    ({ id, title, note }: { id: string; title: string; note: string }) =>
      addProjectOutput(id, { title, note }),
  );
}

export function useDeleteProjectOutput() {
  return useProjectUpdate(({ id, outputId }: { id: string; outputId: string }) =>
    deleteProjectOutput(id, outputId),
  );
}

export function useSaveChatFileAsMaterial() {
  return useProjectUpdate(
    ({ id, threadId, path }: { id: string; threadId: string; path: string }) =>
      saveChatFileAsMaterial(id, { threadId, path }),
  );
}

export function useUploadProjectMaterial() {
  return useProjectUpdate(({ id, file }: { id: string; file: File }) =>
    uploadProjectMaterial(id, file),
  );
}

export function useDeleteProjectMaterial() {
  return useProjectUpdate(
    ({ id, materialId }: { id: string; materialId: string }) =>
      deleteProjectMaterial(id, materialId),
  );
}
