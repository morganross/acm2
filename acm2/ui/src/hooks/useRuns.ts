import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { runsApi, type CreateRunRequest } from '@/api/runs'

export function useRuns(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: ['runs', params],
    queryFn: () => runsApi.list(params),
  })
}

export function useRun(id: string | undefined) {
  return useQuery({
    queryKey: ['runs', id],
    queryFn: () => runsApi.get(id!),
    enabled: !!id,
  })
}

export function useRunProgress(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['runs', id, 'progress'],
    queryFn: () => runsApi.progress(id!),
    enabled: !!id && enabled,
    refetchInterval: enabled ? 2000 : false,
  })
}

export function useCreateRun() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (data: CreateRunRequest) => runsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

export function useCancelRun() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (id: string) => runsApi.cancel(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['runs', id] })
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

export function useDeleteRun() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (id: string) => runsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}
