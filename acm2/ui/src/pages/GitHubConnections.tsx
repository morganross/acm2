import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Github,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  FolderOpen,
  ChevronRight,
  FileText,
  Folder,
  X,
  ArrowLeft,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { notify } from '@/stores/notifications'
import { githubApi, type GitHubConnectionSummary, type GitHubFileInfo } from '@/api/github'

export default function GitHubConnections() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [showBrowseModal, setShowBrowseModal] = useState(false)
  const [browseConnectionId, setBrowseConnectionId] = useState<string | null>(null)
  const [showToken, setShowToken] = useState(false)
  const [addForm, setAddForm] = useState({
    name: '',
    repo: '',
    branch: 'main',
    token: '',
  })

  // Fetch connections list
  const { data: connections, isLoading } = useQuery({
    queryKey: ['github-connections'],
    queryFn: () => githubApi.list(),
  })

  // Create connection mutation
  const createMutation = useMutation({
    mutationFn: githubApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-connections'] })
      setShowAddModal(false)
      setAddForm({ name: '', repo: '', branch: 'main', token: '' })
      notify.success('GitHub connection created')
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : String(error)
      notify.error(`Failed to create connection: ${message}`)
    },
  })

  // Delete connection mutation
  const deleteMutation = useMutation({
    mutationFn: githubApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-connections'] })
      notify.success('Connection deleted')
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : String(error)
      notify.error(`Failed to delete: ${message}`)
    },
  })

  // Test connection mutation
  const testMutation = useMutation({
    mutationFn: githubApi.test,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['github-connections'] })
      if (result.is_valid) {
        notify.success('Connection test passed!')
      } else {
        notify.error(`Connection test failed: ${result.message}`)
      }
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : String(error)
      notify.error(`Test failed: ${message}`)
    },
  })

  const handleCreate = () => {
    if (!addForm.name || !addForm.repo || !addForm.token) {
      notify.warning('Please fill in all required fields')
      return
    }
    createMutation.mutate(addForm)
  }

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete connection "${name}"? This cannot be undone.`)) {
      deleteMutation.mutate(id)
    }
  }

  const handleBrowse = (id: string) => {
    setBrowseConnectionId(id)
    setShowBrowseModal(true)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Github className="h-8 w-8 text-foreground" />
          <div>
            <h1 className="text-2xl font-bold text-foreground">GitHub Connections</h1>
            <p className="text-sm text-muted-foreground">
              Manage repository connections for importing documents
            </p>
          </div>
        </div>
        <Button
          variant="primary"
          icon={<Plus className="h-4 w-4" />}
          onClick={() => setShowAddModal(true)}
        >
          Add Connection
        </Button>
      </div>

      {/* Connections List */}
      <div className="bg-card border rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
            Loading connections...
          </div>
        ) : !connections?.items.length ? (
          <div className="p-8 text-center">
            <Github className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
            <p className="text-muted-foreground">No GitHub connections yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Add a connection to import documents from GitHub
            </p>
            <Button
              variant="outline"
              className="mt-4"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => setShowAddModal(true)}
            >
              Add First Connection
            </Button>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-muted/30 border-b">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-foreground">Name</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-foreground">Repository</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-foreground">Branch</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-foreground">Status</th>
                <th className="text-left px-4 py-3 text-sm font-medium text-foreground">Last Tested</th>
                <th className="text-right px-4 py-3 text-sm font-medium text-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {connections.items.map((conn: GitHubConnectionSummary) => (
                <tr key={conn.id} className="hover:bg-accent/30 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Github className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium text-foreground">{conn.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground font-mono">
                    {conn.repo}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {conn.branch}
                  </td>
                  <td className="px-4 py-3">
                    {conn.is_valid ? (
                      <span className="inline-flex items-center gap-1 text-sm text-green-400">
                        <CheckCircle2 className="h-4 w-4" />
                        Valid
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-sm text-red-400">
                        <XCircle className="h-4 w-4" />
                        Invalid
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {conn.last_tested_at
                      ? new Date(conn.last_tested_at).toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<FolderOpen className="h-4 w-4" />}
                        onClick={() => handleBrowse(conn.id)}
                      >
                        Browse
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<RefreshCw className={cn("h-4 w-4", testMutation.isPending && "animate-spin")} />}
                        onClick={() => testMutation.mutate(conn.id)}
                        disabled={testMutation.isPending}
                      >
                        Test
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 className="h-4 w-4 text-red-400" />}
                        onClick={() => handleDelete(conn.id, conn.name)}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Add Connection Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border rounded-lg w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Add GitHub Connection</h2>
              <Button
                variant="ghost"
                size="sm"
                icon={<X className="h-4 w-4" />}
                onClick={() => setShowAddModal(false)}
              />
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Connection Name *
                </label>
                <input
                  type="text"
                  value={addForm.name}
                  onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                  placeholder="My Research Repo"
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Repository *
                </label>
                <input
                  type="text"
                  value={addForm.repo}
                  onChange={(e) => {
                    let value = e.target.value
                    // Auto-extract owner/repo from GitHub URL
                    const urlMatch = value.match(/github\.com\/([^\/]+\/[^\/]+)/)
                    if (urlMatch) {
                      value = urlMatch[1].replace(/\.git$/, '')
                    }
                    setAddForm({ ...addForm, repo: value })
                  }}
                  placeholder="owner/repository or GitHub URL"
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring font-mono"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Format: owner/repo (e.g., microsoft/vscode) or paste a GitHub URL
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Branch
                </label>
                <input
                  type="text"
                  value={addForm.branch}
                  onChange={(e) => setAddForm({ ...addForm, branch: e.target.value })}
                  placeholder="main"
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Personal Access Token *
                </label>
                <div className="relative">
                  <input
                    type={showToken ? 'text' : 'password'}
                    value={addForm.token}
                    onChange={(e) => setAddForm({ ...addForm, token: e.target.value })}
                    placeholder="ghp_xxxxxxxxxxxx"
                    className="w-full px-3 py-2 pr-10 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Needs repo read access. Create at GitHub → Settings → Developer settings → Personal access tokens
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t">
              <Button variant="ghost" onClick={() => setShowAddModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleCreate}
                loading={createMutation.isPending}
              >
                Add Connection
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Browse Modal */}
      {showBrowseModal && browseConnectionId && (
        <GitHubBrowseModal
          connectionId={browseConnectionId}
          onClose={() => {
            setShowBrowseModal(false)
            setBrowseConnectionId(null)
          }}
        />
      )}
    </div>
  )
}

// Browse Modal Component
function GitHubBrowseModal({
  connectionId,
  onClose,
}: {
  connectionId: string
  onClose: () => void
}) {
  const [currentPath, setCurrentPath] = useState('/')
  const [pathHistory, setPathHistory] = useState<string[]>(['/'])

  const { data: browseData, isLoading } = useQuery({
    queryKey: ['github-browse', connectionId, currentPath],
    queryFn: () => githubApi.browse(connectionId, currentPath),
  })

  const navigateTo = (path: string) => {
    setPathHistory([...pathHistory, path])
    setCurrentPath(path)
  }

  const navigateBack = () => {
    if (pathHistory.length > 1) {
      const newHistory = pathHistory.slice(0, -1)
      setPathHistory(newHistory)
      setCurrentPath(newHistory[newHistory.length - 1])
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-card border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FolderOpen className="h-5 w-5 text-muted-foreground" />
            <div>
              <h2 className="font-semibold text-foreground">Browse Repository</h2>
              <p className="text-sm text-muted-foreground font-mono">{browseData?.repo}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" icon={<X className="h-4 w-4" />} onClick={onClose} />
        </div>

        {/* Path breadcrumb */}
        <div className="px-4 py-2 border-b bg-muted/30 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            icon={<ArrowLeft className="h-4 w-4" />}
            onClick={navigateBack}
            disabled={pathHistory.length <= 1}
          />
          <span className="font-mono text-sm text-muted-foreground">{currentPath}</span>
        </div>

        {/* File list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">
              <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2" />
              Loading...
            </div>
          ) : !browseData?.contents.length ? (
            <div className="p-8 text-center text-muted-foreground">
              Empty directory
            </div>
          ) : (
            <div className="divide-y">
              {browseData.contents
                .sort((a: GitHubFileInfo, b: GitHubFileInfo) => {
                  // Directories first
                  if (a.type === 'dir' && b.type !== 'dir') return -1
                  if (a.type !== 'dir' && b.type === 'dir') return 1
                  return a.name.localeCompare(b.name)
                })
                .map((item: GitHubFileInfo) => (
                  <button
                    key={item.path}
                    onClick={() => {
                      if (item.type === 'dir') {
                        navigateTo(item.path)
                      }
                    }}
                    className={cn(
                      'w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-accent/50 transition-colors',
                      item.type === 'dir' && 'cursor-pointer'
                    )}
                  >
                    {item.type === 'dir' ? (
                      <Folder className="h-5 w-5 text-blue-400" />
                    ) : (
                      <FileText className="h-5 w-5 text-muted-foreground" />
                    )}
                    <span className="flex-1 text-foreground">{item.name}</span>
                    {item.type === 'dir' && (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                    {item.type === 'file' && item.size && (
                      <span className="text-xs text-muted-foreground">
                        {formatFileSize(item.size)}
                      </span>
                    )}
                  </button>
                ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t bg-muted/30">
          <p className="text-xs text-muted-foreground text-center">
            Browse repository contents. Use "Import from GitHub" in Content Library to import files.
          </p>
        </div>
      </div>
    </div>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
