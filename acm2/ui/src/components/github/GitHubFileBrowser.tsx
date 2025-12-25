/**
 * GitHub File Browser Component
 * 
 * A reusable modal component for browsing and selecting files from connected GitHub repos.
 * Can be used for:
 * - Selecting input files from GitHub
 * - Choosing a destination path for exports
 */
import { useState, useEffect } from 'react'
import { 
  Github, 
  FolderOpen, 
  FileText, 
  ChevronRight, 
  Loader2, 
  X, 
  RefreshCw,
  Home,
  Check
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { githubApi, type GitHubConnectionSummary, type GitHubFileInfo } from '@/api/github'

interface GitHubFileBrowserProps {
  /** Whether the modal is open */
  isOpen: boolean
  /** Called when modal should close */
  onClose: () => void
  /** Called when a file is selected (for input selection) */
  onSelectFile?: (connectionId: string, path: string, content: string) => void
  /** Called when a path is selected (for export destination) */
  onSelectPath?: (connectionId: string, path: string) => void
  /** Mode: 'select-file' for input, 'select-path' for export destination */
  mode?: 'select-file' | 'select-path'
  /** Title for the modal */
  title?: string
  /** File extensions to filter (e.g., ['.md', '.txt']) */
  allowedExtensions?: string[]
  /** Default filename for export mode */
  defaultFilename?: string
}

export function GitHubFileBrowser({
  isOpen,
  onClose,
  onSelectFile,
  onSelectPath,
  mode = 'select-file',
  title = 'Select from GitHub',
  allowedExtensions,
  defaultFilename = 'output.md',
}: GitHubFileBrowserProps) {
  const [connections, setConnections] = useState<GitHubConnectionSummary[]>([])
  const [selectedConnection, setSelectedConnection] = useState<string | null>(null)
  const [currentPath, setCurrentPath] = useState('/')
  const [contents, setContents] = useState<GitHubFileInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingConnections, setLoadingConnections] = useState(false)
  const [loadingFile, setLoadingFile] = useState(false)
  const [filename, setFilename] = useState(defaultFilename)
  const [error, setError] = useState<string | null>(null)

  // Load connections when modal opens
  useEffect(() => {
    if (isOpen) {
      loadConnections()
    }
  }, [isOpen])

  // Browse when connection changes
  useEffect(() => {
    if (selectedConnection) {
      browseDirectory('/')
    }
  }, [selectedConnection])

  const loadConnections = async () => {
    setLoadingConnections(true)
    setError(null)
    try {
      const result = await githubApi.list()
      setConnections(result.items.filter(c => c.is_valid))
      if (result.items.length > 0 && result.items.some(c => c.is_valid)) {
        setSelectedConnection(result.items.find(c => c.is_valid)?.id || null)
      }
    } catch (err) {
      setError('Failed to load GitHub connections')
    } finally {
      setLoadingConnections(false)
    }
  }

  const browseDirectory = async (path: string) => {
    if (!selectedConnection) return
    
    setLoading(true)
    setError(null)
    try {
      const result = await githubApi.browse(selectedConnection, path)
      let items = result.contents
      
      // Filter by extensions if specified
      if (allowedExtensions && allowedExtensions.length > 0) {
        items = items.filter(item => {
          if (item.type === 'dir') return true
          return allowedExtensions.some(ext => 
            item.name.toLowerCase().endsWith(ext.toLowerCase())
          )
        })
      }
      
      setContents(items)
      setCurrentPath(path)
    } catch (err) {
      setError('Failed to browse repository')
    } finally {
      setLoading(false)
    }
  }

  const handleFileClick = async (item: GitHubFileInfo) => {
    if (item.type === 'dir') {
      browseDirectory(item.path)
    } else if (mode === 'select-file' && onSelectFile) {
      // Fetch file content and return
      setLoadingFile(true)
      try {
        const file = await githubApi.getFile(selectedConnection!, item.path)
        onSelectFile(selectedConnection!, item.path, file.content)
        onClose()
      } catch (err) {
        setError('Failed to load file content')
      } finally {
        setLoadingFile(false)
      }
    }
  }

  const handleSelectPath = () => {
    if (!selectedConnection || !onSelectPath) return
    const fullPath = currentPath === '/' 
      ? filename 
      : `${currentPath}/${filename}`.replace(/^\//, '')
    onSelectPath(selectedConnection, fullPath)
    onClose()
  }

  const navigateUp = () => {
    const parentPath = currentPath.split('/').slice(0, -1).join('/') || '/'
    browseDirectory(parentPath)
  }

  const pathParts = currentPath === '/' 
    ? [] 
    : currentPath.split('/').filter(Boolean)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Github className="h-5 w-5" />
            <h2 className="font-semibold text-foreground">{title}</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-accent rounded">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Connection Selector */}
        <div className="p-4 border-b bg-muted/50">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-foreground">Repository:</label>
            {loadingConnections ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : connections.length === 0 ? (
              <span className="text-sm text-muted-foreground">
                No GitHub connections. <a href="/settings" className="text-primary hover:underline">Add one in Settings</a>
              </span>
            ) : (
              <select
                value={selectedConnection || ''}
                onChange={(e) => setSelectedConnection(e.target.value)}
                className="flex-1 px-3 py-1.5 border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {connections.map(conn => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.repo})
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={loadConnections}
              className="p-1.5 hover:bg-accent rounded"
              title="Refresh connections"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Breadcrumb */}
        {selectedConnection && (
          <div className="px-4 py-2 border-b flex items-center gap-1 text-sm overflow-x-auto">
            <button
              onClick={() => browseDirectory('/')}
              className="p-1 hover:bg-accent rounded"
              title="Root"
            >
              <Home className="h-4 w-4" />
            </button>
            {pathParts.map((part, i) => (
              <div key={i} className="flex items-center gap-1">
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                <button
                  onClick={() => browseDirectory('/' + pathParts.slice(0, i + 1).join('/'))}
                  className="px-1.5 py-0.5 hover:bg-accent rounded text-foreground"
                >
                  {part}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* File List */}
        <div className="flex-1 overflow-y-auto p-2 min-h-[300px]">
          {error && (
            <div className="p-4 text-center text-red-500 text-sm">{error}</div>
          )}
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : loadingFile ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading file...</span>
            </div>
          ) : !selectedConnection ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Github className="h-12 w-12 mb-4 opacity-50" />
              <p>Select a GitHub connection to browse files</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {currentPath !== '/' && (
                <button
                  onClick={navigateUp}
                  className="w-full flex items-center gap-3 px-3 py-2 hover:bg-accent rounded-md transition-colors"
                >
                  <FolderOpen className="h-4 w-4 text-yellow-500" />
                  <span className="text-foreground">..</span>
                </button>
              )}
              
              {contents.map(item => (
                <button
                  key={item.path}
                  onClick={() => handleFileClick(item)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 hover:bg-accent rounded-md transition-colors",
                    item.type === 'file' && mode === 'select-file' && "cursor-pointer",
                    item.type === 'file' && mode === 'select-path' && "opacity-50 cursor-default"
                  )}
                  disabled={item.type === 'file' && mode === 'select-path'}
                >
                  {item.type === 'dir' ? (
                    <FolderOpen className="h-4 w-4 text-yellow-500" />
                  ) : (
                    <FileText className="h-4 w-4 text-blue-400" />
                  )}
                  <span className="flex-1 text-left text-foreground">{item.name}</span>
                  {item.size !== null && (
                    <span className="text-xs text-muted-foreground">
                      {item.size > 1024 ? `${(item.size / 1024).toFixed(1)} KB` : `${item.size} B`}
                    </span>
                  )}
                  {item.type === 'dir' && (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
              ))}
              
              {contents.length === 0 && (
                <div className="py-8 text-center text-muted-foreground text-sm">
                  Empty directory
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer for select-path mode */}
        {mode === 'select-path' && selectedConnection && (
          <div className="p-4 border-t bg-muted/50">
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-foreground">Filename:</label>
              <input
                type="text"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                placeholder="filename.md"
                className="flex-1 px-3 py-1.5 border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                onClick={handleSelectPath}
                disabled={!filename.trim()}
                className="inline-flex items-center gap-2 px-4 py-1.5 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 text-sm"
              >
                <Check className="h-4 w-4" />
                Select Path
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Will save to: <code className="bg-background px-1 rounded">
                {currentPath === '/' ? filename : `${currentPath}/${filename}`.replace(/^\//, '')}
              </code>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default GitHubFileBrowser
