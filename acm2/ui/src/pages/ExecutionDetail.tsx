import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Clock, Play, CheckCircle, AlertCircle, RefreshCw, FileText } from 'lucide-react'
import { useRun } from '@/hooks/useRuns'
import useRunSocket from '@/hooks/useRunSocket'
import { API_BASE_URL } from '@/api/client'

export default function RunDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: run, isLoading } = useRun(id)
  useRunSocket(id)

  const handleDownloadReport = () => {
    window.open(`${API_BASE_URL}/runs/${id}/report`, '_blank')
  }

  if (!run || isLoading) {
    return (
      <div className="space-y-6">
        <Link
          to="/runs"
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Runs
        </Link>

        <div className="bg-card border rounded-lg p-12 text-center">
          <AlertCircle className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">Run not found</p>
          <p className="text-sm text-muted-foreground mt-1">
            The run with ID "{id}" could not be found
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/runs"
            className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Run Details</h1>
            <p className="text-sm text-muted-foreground">ID: {id}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {run.status === 'completed' && (
            <button 
              onClick={handleDownloadReport}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
            >
              <FileText className="h-4 w-4" />
              View Report
            </button>
          )}
          <button className="inline-flex items-center gap-2 px-4 py-2 border rounded-md text-foreground hover:bg-accent transition-colors">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Status Overview */}
      <div className="bg-card border rounded-lg p-4">
        <h2 className="font-semibold text-foreground mb-4">Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-3 bg-muted rounded-md">
            <Play className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm text-muted-foreground">Mode</p>
              <p className="font-medium text-foreground">{(run && run.mode) ? run.mode : 'Full Pipeline'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-muted rounded-md">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <p className="font-medium text-foreground">{run?.status ?? 'Pending'}</p>
              {run?.current_phase && (
                <p className="text-xs text-muted-foreground">Phase: {run.current_phase}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-muted rounded-md">
            <CheckCircle className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm text-muted-foreground">Progress</p>
              <p className="font-medium text-foreground">{run?.progress?.completed_tasks ?? 0} / {run?.progress?.total_tasks ?? 0} docs</p>
            </div>
          </div>
        </div>
      </div>

      {/* Document Progress */}
      <div className="bg-card border rounded-lg">
        <div className="px-4 py-3 border-b">
          <h2 className="font-semibold text-foreground">Document Progress</h2>
        </div>
        {run?.tasks && run.tasks.length ? (
          <div className="p-4">
            <ul className="space-y-2">
              {run.tasks.map((t: any) => (
                <li key={t.id} className="flex items-center justify-between p-2 border rounded-md">
                  <div>
                    <div className="text-sm font-medium">{t.document_name}</div>
                    <div className="text-xs text-muted-foreground">{t.generator} / {t.model} #{t.iteration}</div>
                  </div>
                  <div className="text-sm font-medium text-right">
                    <div>{t.status}</div>
                    {t.progress !== undefined && (
                      <div className="text-xs text-muted-foreground">{Math.round((t.progress || 0) * 100)}% {t.message ? `— ${t.message}` : ''}</div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="p-8 text-center text-muted-foreground">
            <p>No documents in this run</p>
          </div>
        )}
      </div>

      {/* Logs */}
      <div className="bg-card border rounded-lg">
        <div className="px-4 py-3 border-b">
          <h2 className="font-semibold text-foreground">Logs</h2>
        </div>
        <div className="p-4 bg-muted/50 font-mono text-sm text-muted-foreground max-h-64 overflow-auto">
          <p>Waiting for logs...</p>
        </div>
      </div>
    </div>
  )
}
