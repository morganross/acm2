import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileText,
  Search,
  Plus,
  Trash2,
  Copy,
  Save,
  X,
  Tag,
  Code,
  FileInput,
  FileOutput,
  CheckCircle2,
  Scroll,
  GitBranch,
  ChevronRight,
  Github,
  Folder,
  ArrowLeft,
  RefreshCw,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { contentsApi, ContentType, ContentTypeCounts } from '@/api/contents'
import { githubApi, type GitHubConnectionSummary, type GitHubFileInfo } from '@/api/github'

// Content type metadata for display
const contentTypeInfo: Record<ContentType, { label: string; icon: React.ReactNode; description: string }> = {
  generation_instructions: {
    label: 'Generation Instructions',
    icon: <FileOutput className="h-4 w-4" />,
    description: 'Instructions for document generation',
  },
  input_document: {
    label: 'Input Documents',
    icon: <FileInput className="h-4 w-4" />,
    description: 'Source documents to process',
  },
  single_eval_instructions: {
    label: 'Single Eval Instructions',
    icon: <CheckCircle2 className="h-4 w-4" />,
    description: 'Instructions for single document evaluation',
  },
  pairwise_eval_instructions: {
    label: 'Pairwise Eval Instructions',
    icon: <Code className="h-4 w-4" />,
    description: 'Instructions for pairwise comparison',
  },
  eval_criteria: {
    label: 'Evaluation Criteria',
    icon: <Scroll className="h-4 w-4" />,
    description: 'Criteria definitions for evaluation',
  },
  combine_instructions: {
    label: 'Combine Instructions',
    icon: <GitBranch className="h-4 w-4" />,
    description: 'Instructions for combining results',
  },
  template_fragment: {
    label: 'Template Fragments',
    icon: <Tag className="h-4 w-4" />,
    description: 'Reusable template snippets',
  },
}

// Parse variables from content body
function parseVariables(body: string): string[] {
  const regex = /\{\{(\w+)\}\}/g
  const vars: string[] = []
  let match
  while ((match = regex.exec(body)) !== null) {
    if (!vars.includes(match[1])) {
      vars.push(match[1])
    }
  }
  return vars
}

// Highlight variables in text
function highlightVariables(text: string): React.ReactNode[] {
  const parts = text.split(/(\{\{\w+\}\})/g)
  return parts.map((part, i) => {
    if (part.match(/^\{\{\w+\}\}$/)) {
      return (
        <span key={i} className="bg-yellow-500/30 text-yellow-300 px-1 rounded">
          {part}
        </span>
      )
    }
    return part
  })
}

// Keep for potential future use
void highlightVariables

export default function ContentLibrary() {
  const queryClient = useQueryClient()
  const [selectedType, setSelectedType] = useState<ContentType | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedContentId, setSelectedContentId] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [showGitHubImport, setShowGitHubImport] = useState(false)
  const [editForm, setEditForm] = useState<{
    name: string
    content_type: ContentType
    body: string
    tags: string
  }>({
    name: '',
    content_type: 'generation_instructions',
    body: '',
    tags: '',
  })

  // Fetch content counts by type
  const { data: counts } = useQuery({
    queryKey: ['contentCounts'],
    queryFn: contentsApi.counts,
  })

  // Fetch content list
  const { data: contents, isLoading } = useQuery({
    queryKey: ['contents', selectedType, searchQuery],
    queryFn: () =>
      contentsApi.list({
        content_type: selectedType === 'all' ? undefined : selectedType,
        search: searchQuery || undefined,
        page_size: 100,
      }),
  })

  // Fetch selected content detail
  const { data: selectedContent } = useQuery({
    queryKey: ['content', selectedContentId],
    queryFn: () => (selectedContentId ? contentsApi.get(selectedContentId) : null),
    enabled: !!selectedContentId,
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: contentsApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['contentCounts'] })
      setIsCreating(false)
      setSelectedContentId(data.id)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof contentsApi.update>[1] }) =>
      contentsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['content', selectedContentId] })
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: contentsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['contentCounts'] })
      setSelectedContentId(null)
    },
  })

  // Duplicate mutation
  const duplicateMutation = useMutation({
    mutationFn: (id: string) => contentsApi.duplicate(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['contents'] })
      queryClient.invalidateQueries({ queryKey: ['contentCounts'] })
      setSelectedContentId(data.id)
    },
  })

  // Update edit form when selected content changes
  useEffect(() => {
    if (selectedContent) {
      setEditForm({
        name: selectedContent.name,
        content_type: selectedContent.content_type,
        body: selectedContent.body,
        tags: selectedContent.tags.join(', '),
      })
    }
  }, [selectedContent])

  // Reset form when creating
  useEffect(() => {
    if (isCreating) {
      setEditForm({
        name: '',
        content_type: selectedType === 'all' ? 'generation_instructions' : selectedType,
        body: '',
        tags: '',
      })
      setSelectedContentId(null)
    }
  }, [isCreating, selectedType])

  // Computed variables from body
  const detectedVariables = useMemo(() => parseVariables(editForm.body), [editForm.body])

  const handleSave = () => {
    const tags = editForm.tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    if (isCreating) {
      createMutation.mutate({
        name: editForm.name,
        content_type: editForm.content_type,
        body: editForm.body,
        tags,
      })
    } else if (selectedContentId) {
      updateMutation.mutate({
        id: selectedContentId,
        data: {
          name: editForm.name,
          body: editForm.body,
          tags,
        },
      })
    }
  }

  const handleDelete = () => {
    if (selectedContentId && confirm('Delete this content? This cannot be undone.')) {
      deleteMutation.mutate(selectedContentId)
    }
  }

  const handleDuplicate = () => {
    if (selectedContentId) {
      duplicateMutation.mutate(selectedContentId)
    }
  }

  const contentTypeOptions = Object.entries(contentTypeInfo) as [ContentType, typeof contentTypeInfo[ContentType]][]

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sidebar - Content Types */}
      <div className="w-56 flex-shrink-0 bg-card border rounded-lg overflow-hidden">
        <div className="p-3 border-b bg-muted/30">
          <h2 className="font-semibold text-sm text-foreground">Content Types</h2>
        </div>
        <nav className="p-2 space-y-1">
          <button
            onClick={() => setSelectedType('all')}
            className={cn(
              'w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors',
              selectedType === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            )}
          >
            <span className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              All Content
            </span>
            <span className="text-xs opacity-70">
              {counts?.total ?? 0}
            </span>
          </button>
          {contentTypeOptions.map(([type, info]) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={cn(
                'w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors',
                selectedType === type
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              )}
            >
              <span className="flex items-center gap-2">
                {info.icon}
                <span className="truncate">{info.label}</span>
              </span>
              <span className="text-xs opacity-70">{counts ? counts[type as keyof ContentTypeCounts] || 0 : 0}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Content List */}
      <div className="w-72 flex-shrink-0 bg-card border rounded-lg overflow-hidden flex flex-col">
        <div className="p-3 border-b bg-muted/30 space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm text-foreground">
              {selectedType === 'all' ? 'All Content' : contentTypeInfo[selectedType].label}
            </h2>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                icon={<Github className="h-4 w-4" />}
                onClick={() => setShowGitHubImport(true)}
                title="Import from GitHub"
              />
              <Button
                variant="ghost"
                size="sm"
                icon={<Plus className="h-4 w-4" />}
                onClick={() => setIsCreating(true)}
              >
                New
              </Button>
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground">Loading...</div>
          ) : contents?.items.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">
              <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No content yet</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                icon={<Plus className="h-4 w-4" />}
                onClick={() => setIsCreating(true)}
              >
                Create First
              </Button>
            </div>
          ) : (
            <div className="divide-y">
              {contents?.items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setIsCreating(false)
                    setSelectedContentId(item.id)
                  }}
                  className={cn(
                    'w-full text-left p-3 hover:bg-accent/50 transition-colors',
                    selectedContentId === item.id && !isCreating && 'bg-accent'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm text-foreground truncate">{item.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {contentTypeInfo[item.content_type]?.label}
                      </p>
                      {item.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {item.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-blue-500/20 text-blue-300"
                            >
                              {tag}
                            </span>
                          ))}
                          {item.tags.length > 3 && (
                            <span className="text-xs text-muted-foreground">+{item.tags.length - 3}</span>
                          )}
                        </div>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Editor Panel */}
      <div className="flex-1 bg-card border rounded-lg overflow-hidden flex flex-col">
        {isCreating || selectedContentId ? (
          <>
            <div className="p-3 border-b bg-muted/30 flex items-center justify-between">
              <h2 className="font-semibold text-sm text-foreground">
                {isCreating ? 'New Content' : 'Edit Content'}
              </h2>
              <div className="flex items-center gap-2">
                {!isCreating && (
                  <>
                    <Button variant="ghost" size="sm" icon={<Copy className="h-4 w-4" />} onClick={handleDuplicate}>
                      Duplicate
                    </Button>
                    <Button variant="ghost" size="sm" icon={<Trash2 className="h-4 w-4" />} onClick={handleDelete}>
                      Delete
                    </Button>
                  </>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<X className="h-4 w-4" />}
                  onClick={() => {
                    setIsCreating(false)
                    setSelectedContentId(null)
                  }}
                >
                  Close
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Save className="h-4 w-4" />}
                  onClick={handleSave}
                  loading={createMutation.isPending || updateMutation.isPending}
                >
                  Save
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Name</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  placeholder="Enter content name..."
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              {/* Content Type (only for new) */}
              {isCreating && (
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Content Type</label>
                  <select
                    value={editForm.content_type}
                    onChange={(e) => setEditForm({ ...editForm, content_type: e.target.value as ContentType })}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {contentTypeOptions.map(([type, info]) => (
                      <option key={type} value={type}>
                        {info.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Tags */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Tags (comma separated)</label>
                <input
                  type="text"
                  value={editForm.tags}
                  onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                  placeholder="tag1, tag2, tag3..."
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              {/* Body / Content Editor */}
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-foreground">Content Body</label>
                  {detectedVariables.length > 0 && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Code className="h-3 w-3" />
                      <span>Variables:</span>
                      {detectedVariables.map((v) => (
                        <span key={v} className="bg-yellow-500/30 text-yellow-300 px-1 rounded">
                          {v}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <textarea
                  value={editForm.body}
                  onChange={(e) => setEditForm({ ...editForm, body: e.target.value })}
                  placeholder="Enter content... Use {{VARIABLE}} syntax for variables that will be substituted at runtime."
                  rows={15}
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring font-mono text-sm resize-none"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Use <code className="bg-muted px-1 rounded">{'{{VARIABLE}}'}</code> syntax for template variables.
                </p>
              </div>

              {/* Stored Variables (read-only display) */}
              {selectedContent?.variables && Object.keys(selectedContent.variables).length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Stored Variables</label>
                  <div className="bg-muted/50 rounded-md p-3 font-mono text-sm">
                    {Object.entries(selectedContent.variables).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <span className="text-yellow-300">{key}:</span>
                        <span className="text-foreground">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <FileText className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground">Select content to edit</p>
              <p className="text-sm text-muted-foreground mt-1">or create new content</p>
              <Button
                variant="outline"
                className="mt-4"
                icon={<Plus className="h-4 w-4" />}
                onClick={() => setIsCreating(true)}
              >
                Create New Content
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* GitHub Import Modal */}
      {showGitHubImport && (
        <GitHubImportModal
          defaultContentType={selectedType === 'all' ? 'input_document' : selectedType}
          onClose={() => setShowGitHubImport(false)}
          onImported={(contentId) => {
            queryClient.invalidateQueries({ queryKey: ['contents'] })
            queryClient.invalidateQueries({ queryKey: ['contentCounts'] })
            setShowGitHubImport(false)
            setSelectedContentId(contentId)
          }}
        />
      )}
    </div>
  )
}

// ============================================================================
// GitHub Import Modal Component
// ============================================================================

function GitHubImportModal({
  defaultContentType,
  onClose,
  onImported,
}: {
  defaultContentType: ContentType
  onClose: () => void
  onImported: (contentId: string) => void
}) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)
  const [currentPath, setCurrentPath] = useState('/')
  const [pathHistory, setPathHistory] = useState<string[]>(['/'])
  const [selectedFile, setSelectedFile] = useState<GitHubFileInfo | null>(null)
  const [importContentType, setImportContentType] = useState<ContentType>(defaultContentType)
  const [importName, setImportName] = useState('')
  const [isImporting, setIsImporting] = useState(false)

  // Fetch available connections
  const { data: connections } = useQuery({
    queryKey: ['github-connections'],
    queryFn: () => githubApi.list(),
  })

  // Fetch directory contents
  const { data: browseData, isLoading: isBrowsing } = useQuery({
    queryKey: ['github-browse', selectedConnectionId, currentPath],
    queryFn: () => selectedConnectionId ? githubApi.browse(selectedConnectionId, currentPath) : null,
    enabled: !!selectedConnectionId,
  })

  const navigateTo = (path: string) => {
    setPathHistory([...pathHistory, path])
    setCurrentPath(path)
    setSelectedFile(null)
  }

  const navigateBack = () => {
    if (pathHistory.length > 1) {
      const newHistory = pathHistory.slice(0, -1)
      setPathHistory(newHistory)
      setCurrentPath(newHistory[newHistory.length - 1])
      setSelectedFile(null)
    }
  }

  const handleImport = async () => {
    if (!selectedConnectionId || !selectedFile) return
    
    setIsImporting(true)
    try {
      const result = await githubApi.importFile(selectedConnectionId, {
        path: selectedFile.path,
        content_type: importContentType,
        name: importName || selectedFile.name.replace(/\.[^.]+$/, ''),
      })
      onImported(result.id)
    } catch (error) {
      console.error('Import failed:', error)
      alert(`Import failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setIsImporting(false)
    }
  }

  const contentTypeOptions = Object.entries(contentTypeInfo) as [ContentType, typeof contentTypeInfo[ContentType]][]

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-card border rounded-lg w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Github className="h-5 w-5 text-foreground" />
            <div>
              <h2 className="font-semibold text-foreground">Import from GitHub</h2>
              <p className="text-sm text-muted-foreground">Select a file to import into Content Library</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" icon={<X className="h-4 w-4" />} onClick={onClose} />
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Left side: File browser */}
          <div className="w-2/3 border-r flex flex-col">
            {/* Connection selector */}
            <div className="p-3 border-b bg-muted/30">
              <label className="block text-xs text-muted-foreground mb-1">Connection</label>
              <select
                value={selectedConnectionId || ''}
                onChange={(e) => {
                  setSelectedConnectionId(e.target.value || null)
                  setCurrentPath('/')
                  setPathHistory(['/'])
                  setSelectedFile(null)
                }}
                className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring text-sm"
              >
                <option value="">-- Select Connection --</option>
                {connections?.items.map((conn: GitHubConnectionSummary) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.repo})
                  </option>
                ))}
              </select>
              {!connections?.items.length && (
                <p className="text-xs text-muted-foreground mt-1">
                  No connections. <a href="/github" className="text-primary hover:underline">Add one first</a>
                </p>
              )}
            </div>

            {/* Path breadcrumb */}
            {selectedConnectionId && (
              <div className="px-3 py-2 border-b bg-muted/20 flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<ArrowLeft className="h-4 w-4" />}
                  onClick={navigateBack}
                  disabled={pathHistory.length <= 1}
                />
                <span className="font-mono text-xs text-muted-foreground truncate">{currentPath}</span>
              </div>
            )}

            {/* File list */}
            <div className="flex-1 overflow-y-auto">
              {!selectedConnectionId ? (
                <div className="p-8 text-center text-muted-foreground">
                  <Github className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Select a connection to browse</p>
                </div>
              ) : isBrowsing ? (
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
                          } else {
                            setSelectedFile(item)
                            setImportName(item.name.replace(/\.[^.]+$/, ''))
                          }
                        }}
                        className={cn(
                          'w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-accent/50 transition-colors text-sm',
                          selectedFile?.path === item.path && 'bg-primary/20'
                        )}
                      >
                        {item.type === 'dir' ? (
                          <Folder className="h-4 w-4 text-blue-400 flex-shrink-0" />
                        ) : (
                          <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        )}
                        <span className="flex-1 text-foreground truncate">{item.name}</span>
                        {item.type === 'dir' && (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                      </button>
                    ))}
                </div>
              )}
            </div>
          </div>

          {/* Right side: Import options */}
          <div className="w-1/3 p-4 flex flex-col">
            <h3 className="font-medium text-foreground mb-4">Import Options</h3>
            
            {selectedFile ? (
              <div className="space-y-4 flex-1">
                <div className="p-3 bg-muted/30 rounded-md">
                  <p className="text-xs text-muted-foreground">Selected file</p>
                  <p className="font-mono text-sm text-foreground truncate">{selectedFile.name}</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Name</label>
                  <input
                    type="text"
                    value={importName}
                    onChange={(e) => setImportName(e.target.value)}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">Content Type</label>
                  <select
                    value={importContentType}
                    onChange={(e) => setImportContentType(e.target.value as ContentType)}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring text-sm"
                  >
                    {contentTypeOptions.map(([type, info]) => (
                      <option key={type} value={type}>{info.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-center text-muted-foreground">
                <div>
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Select a file to import</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-muted/30 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            icon={<Download className="h-4 w-4" />}
            onClick={handleImport}
            disabled={!selectedFile || isImporting}
            loading={isImporting}
          >
            Import
          </Button>
        </div>
      </div>
    </div>
  )
}
