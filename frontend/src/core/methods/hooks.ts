import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createMethod, deleteMethod, listMethods } from "./api";

export function useMethods() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["methods"],
    queryFn: listMethods,
  });
  return { methods: data ?? [], isLoading, error };
}

export function useCreateMethod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createMethod,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["methods"] });
    },
  });
}

export function useDeleteMethod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteMethod,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["methods"] });
    },
  });
}
