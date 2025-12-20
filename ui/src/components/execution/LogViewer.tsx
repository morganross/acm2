import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronDown, ChevronUp, Terminal, RefreshCw, Download } from 'lucide-react'
import { apiClient } from '../../api'

interface LogViewerProps {
  runId: string | null
  isRunning: boolean
  logLevel?: string
}

interface LogResponse {
  run_id: string
  log_level: string
  total_lines: number
  offset: number
  lines: string[]
  fpf_available: boolean
  fpf_lines?: string[] | null
}

export default function LogViewer({ runId, isRunning, logLevel = 'INFO' }: LogViewerProps) {
  const [expanded, setExpanded] = useState(false)
  const [logs, setLogs] = useState<string>('')
  const [fpfLogs, setFpfLogs] = useState<string>('')
  const [isPolling, setIsPolling] = useState(false)
  const [activeTab, setActiveTab] = useState<'main' | 'fpf'>('main')
  const logsEndRef = useRef<HTMLDivElement>(null)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Use ref for offset to avoid stale closure in setInterval
  const offsetRef = useRef(0)

  // Scroll to bottom when new logs arrive
  useEffect(() => {
    if (expanded && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, fpfLogs, expanded])

  // Fetch logs - using useCallback and ref to avoid stale closure
  const fetchLogs = useCallback(async () => {
    if (!runId) return
    
    try {
      const response = await apiClient.get<LogResponse>(`/runs/${runId}/logs`, { 
        offset: offsetRef.current,
        include_fpf: logLevel === 'VERBOSE'
      })
      if (response.lines && response.lines.length > 0) {
        setLogs(prev => prev + (prev ? '\n' : '') + response.lines.join('\n'))
        offsetRef.current = response.offset + response.lines.length
      }
      if (response.fpf_lines && response.fpf_lines.length > 0) {
        setFpfLogs(response.fpf_lines.join('\n'))
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    }
  }, [runId, logLevel])

  // Track previous isRunning to detect completion
  const prevIsRunningRef = useRef(isRunning)

  // Polling when running
  useEffect(() => {
    if (isRunning && expanded) {
      setIsPolling(true)
      // Call immediately and then set up interval
      fetchLogs()
      pollIntervalRef.current = setInterval(fetchLogs, 2000)
    } else {
      setIsPolling(false)
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      // Fetch final logs when run completes (isRunning goes from true to false)
      if (prevIsRunningRef.current && !isRunning && expanded && runId) {
        // Small delay to ensure all logs are written
        setTimeout(() => fetchLogs(), 500)
      }
    }
    prevIsRunningRef.current = isRunning
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [isRunning, expanded, runId, fetchLogs])

  // Fetch once when expanded
  useEffect(() => {
    if (expanded && runId) {
      fetchLogs()
    }
  }, [expanded, runId])

  // Reset when run changes
  useEffect(() => {
    setLogs('')
    setFpfLogs('')
    offsetRef.current = 0
  }, [runId])

  const handleDownload = () => {
    const content = activeTab === 'main' ? logs : fpfLogs
    const filename = activeTab === 'main' ? `run_${runId}_logs.txt` : `run_${runId}_fpf_output.txt`
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const showFpfTab = logLevel === 'VERBOSE'

  if (!runId) {
    return null
  }

  return (
    <div className="mt-4 border rounded-lg bg-gray-900 text-gray-100">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-800 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="font-medium">Execution Logs</span>
          {isPolling && (
            <RefreshCw className="w-3 h-3 text-blue-400 animate-spin" />
          )}
          <span className="text-xs text-gray-500 ml-2">
            Level: {logLevel}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronUp className="w-4 h-4" />
        )}
      </button>

      {/* Content */}
      {expanded && (
        <div className="border-t border-gray-700">
          {/* Tabs */}
          {showFpfTab && (
            <div className="flex border-b border-gray-700">
              <button
                onClick={() => setActiveTab('main')}
                className={`px-4 py-2 text-sm ${
                  activeTab === 'main'
                    ? 'bg-gray-800 text-white border-b-2 border-emerald-500'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Main Logs
              </button>
              <button
                onClick={() => setActiveTab('fpf')}
                className={`px-4 py-2 text-sm ${
                  activeTab === 'fpf'
                    ? 'bg-gray-800 text-white border-b-2 border-emerald-500'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                FPF Output
              </button>
              <div className="flex-1" />
              <button
                onClick={handleDownload}
                className="px-3 py-2 text-gray-400 hover:text-white"
                title="Download logs"
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Log content */}
          <div className="h-64 overflow-y-auto p-4 font-mono text-xs">
            {activeTab === 'main' ? (
              logs ? (
                <pre className="whitespace-pre-wrap break-words">{logs}</pre>
              ) : (
                <span className="text-gray-500">No logs available yet...</span>
              )
            ) : (
              fpfLogs ? (
                <pre className="whitespace-pre-wrap break-words">{fpfLogs}</pre>
              ) : (
                <span className="text-gray-500">
                  No FPF output. FPF output is only captured when log level is VERBOSE.
                </span>
              )
            )}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}
    </div>
  )
}
