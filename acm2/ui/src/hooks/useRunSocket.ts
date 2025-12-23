import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

type RunSocketHandlers = {
  onRunUpdate?: (run: any) => void
  onTaskUpdate?: (task: any) => void
  onTasksInit?: (tasks: any[]) => void
  onStatsUpdate?: (stats: any) => void
  onGenComplete?: (genDoc: { id: string; model: string; generator: string; source_doc_id: string; iteration: number }) => void
}

export function useRunSocket(runId?: string, handlers: RunSocketHandlers = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()
  const { onRunUpdate, onTaskUpdate, onTasksInit, onStatsUpdate, onGenComplete } = handlers

  useEffect(() => {
    if (!runId) return
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${protocol}://${host}/api/v1/runs/ws/run/${runId}`
    console.log('[WS] Connecting to:', url)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[WS] Connected to run:', runId)
    }

        ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        // If the server sends the full run object, update the cache
        if (msg.run) {
          queryClient.setQueryData(['runs', runId], msg.run)
          queryClient.setQueryData(['runs'], (old: any) => {
            if (!old || !old.items) return old
            return {
              ...old,
              items: old.items.map((r: any) => (r.id === runId ? msg.run : r)),
            }
          })
          onRunUpdate?.(msg.run)
          return
        }

        // If we get a task update, merge it into the cached run
        if (msg.task) {
          queryClient.setQueryData(['runs', runId], (oldRun: any) => {
            if (!oldRun) return oldRun
            const tasks = (oldRun.tasks || []).map((t: any) => (t.id === msg.task.id ? { ...t, ...msg.task } : t))
            return { ...oldRun, tasks }
          })
          queryClient.setQueryData(['runs'], (old: any) => {
            if (!old || !old.items) return old
            return { ...old, items: old.items.map((r: any) => (r.id === runId ? { ...r, tasks: (r.tasks || []).map((t: any) => (t.id === msg.task.id ? { ...t, ...msg.task } : t)) } : r)) }
          })
          onTaskUpdate?.(msg.task)
        }

        // If we get an initial tasks list
        if (msg.tasks) {
          queryClient.setQueryData(['runs', runId], (oldRun: any) => {
            if (!oldRun) return oldRun
            return { ...oldRun, tasks: msg.tasks }
          })
          queryClient.setQueryData(['runs'], (old: any) => {
            if (!old || !old.items) return old
            return { ...old, items: old.items.map((r: any) => (r.id === runId ? { ...r, tasks: msg.tasks } : r)) }
          })
          onTasksInit?.(msg.tasks)
        }
        
        // Handle FPF stats updates
        if (msg.event === 'fpf_stats_update' && msg.stats) {
          queryClient.setQueryData(['runs', runId], (oldRun: any) => {
            if (!oldRun) return oldRun
            return { ...oldRun, fpf_stats: msg.stats }
          })
          onStatsUpdate?.(msg.stats)
        }

        // Handle generation completions - add doc to generated_docs for live heatmap rows
        if (msg.event === 'gen_complete') {
          const genDoc = {
            id: msg.doc_id,
            model: msg.model,
            generator: msg.generator,
            source_doc_id: msg.source_doc_id,
            iteration: msg.iteration,
          }
          queryClient.setQueryData(['runs', runId], (oldRun: any) => {
            if (!oldRun) return oldRun
            const generatedDocs = oldRun.generated_docs || []
            // Avoid duplicates
            if (generatedDocs.some((d: any) => d.id === msg.doc_id)) {
              return oldRun
            }
            return { ...oldRun, generated_docs: [...generatedDocs, genDoc] }
          })
          onGenComplete?.(genDoc)
        }
      } catch (e) {
        // console.error('Invalid run ws message', e)
      }
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    return () => {
      try {
        ws.close()
      } catch (_e) {}
    }
  }, [runId, queryClient])
}

export default useRunSocket
