import { useState, useEffect } from 'react'
import { Save, RotateCcw, Key, Database, Zap, Info, Github, Plus, Trash2, RefreshCw, CheckCircle, XCircle, ExternalLink, FolderOpen, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { notify } from '@/stores/notifications'
import { githubApi, type GitHubConnectionSummary, type GitHubFileInfo } from '@/api/github'

// Concurrency settings interface
export interface ConcurrencySettings {
  generationConcurrency: number
  evalConcurrency: number
  requestTimeout: number | null
  evalTimeout: number | null
  maxRetries: number
  retryDelay: number
  iterations: number
  evalIterations: number
  fpfLogOutput: 'stream' | 'file' | 'none'
  fpfLogFilePath: string
  fpfMaxRetries: number
  fpfRetryDelay: number
  postCombineTopN: number | null
}

const defaultConcurrency: ConcurrencySettings = {
  generationConcurrency: 5,
  evalConcurrency: 5,
  requestTimeout: null,
  evalTimeout: null,
  maxRetries: 3,
  retryDelay: 2.0,
  iterations: 1,
  evalIterations: 1,
  fpfLogOutput: 'file',
  fpfLogFilePath: 'logs/{run_id}/fpf_output.log',
  fpfMaxRetries: 3,
  fpfRetryDelay: 1.0,
  postCombineTopN: 5,  // Enable post-combine eval by default
}

// Helper to load settings from localStorage
function loadConcurrencySettings(): ConcurrencySettings {
  try {
    const stored = localStorage.getItem('acm_concurrency_settings')
    if (stored) {
      return { ...defaultConcurrency, ...JSON.parse(stored) }
    }
  } catch (e) {
    console.error('Failed to load concurrency settings:', e)
  }
  return defaultConcurrency
}

// Export for use in other components
export function getConcurrencySettings(): ConcurrencySettings {
  return loadConcurrencySettings()
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<'api' | 'defaults' | 'advanced' | 'github'>('api')
  const [openaiKey, setOpenaiKey] = useState(localStorage.getItem('acm_api_key') || '')
  const [concurrency, setConcurrency] = useState<ConcurrencySettings>(loadConcurrencySettings)
  
  // GitHub state
  const [githubConnections, setGithubConnections] = useState<GitHubConnectionSummary[]>([])
  const [loadingConnections, setLoadingConnections] = useState(false)
  const [showAddConnection, setShowAddConnection] = useState(false)
  const [newConnection, setNewConnection] = useState({ name: '', repo: '', branch: 'main', token: '' })
  const [addingConnection, setAddingConnection] = useState(false)
  const [testingConnection, setTestingConnection] = useState<string | null>(null)
  const [browsingConnection, setBrowsingConnection] = useState<string | null>(null)
  const [browsePath, setBrowsePath] = useState('/')
  const [browseContents, setBrowseContents] = useState<GitHubFileInfo[]>([])
  const [loadingBrowse, setLoadingBrowse] = useState(false)
  
  // Load GitHub connections when tab is activated
  useEffect(() => {
    if (activeTab === 'github') {
      loadGithubConnections()
    }
  }, [activeTab])
  
  const loadGithubConnections = async () => {
    setLoadingConnections(true)
    try {
      const result = await githubApi.list()
      setGithubConnections(result.items)
    } catch (error) {
      console.error('Failed to load GitHub connections:', error)
      notify.error('Failed to load GitHub connections')
    } finally {
      setLoadingConnections(false)
    }
  }
  
  const handleAddConnection = async () => {
    if (!newConnection.name || !newConnection.repo || !newConnection.token) {
      notify.error('Please fill in all required fields')
      return
    }
    
    setAddingConnection(true)
    try {
      await githubApi.create({
        name: newConnection.name,
        repo: newConnection.repo,
        branch: newConnection.branch || 'main',
        token: newConnection.token,
      })
      notify.success('GitHub connection added')
      setShowAddConnection(false)
      setNewConnection({ name: '', repo: '', branch: 'main', token: '' })
      loadGithubConnections()
    } catch (error: unknown) {
      const err = error as { message?: string }
      notify.error(err.message || 'Failed to add connection')
    } finally {
      setAddingConnection(false)
    }
  }
  
  const handleTestConnection = async (id: string) => {
    setTestingConnection(id)
    try {
      const result = await githubApi.test(id)
      if (result.is_valid) {
        notify.success(result.message)
      } else {
        notify.error(result.message)
      }
      loadGithubConnections()
    } catch (error) {
      notify.error('Failed to test connection')
    } finally {
      setTestingConnection(null)
    }
  }
  
  const handleDeleteConnection = async (id: string) => {
    if (!confirm('Delete this GitHub connection?')) return
    
    try {
      await githubApi.delete(id)
      notify.success('Connection deleted')
      loadGithubConnections()
    } catch (error) {
      notify.error('Failed to delete connection')
    }
  }
  
  const handleBrowseConnection = async (id: string, path = '/') => {
    setBrowsingConnection(id)
    setBrowsePath(path)
    setLoadingBrowse(true)
    try {
      const result = await githubApi.browse(id, path)
      setBrowseContents(result.contents)
    } catch (error) {
      notify.error('Failed to browse repository')
      setBrowsingConnection(null)
    } finally {
      setLoadingBrowse(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <div className="flex gap-2">
          <button onClick={() => {
            // Reset to defaults
            localStorage.removeItem('acm_api_key')
            localStorage.removeItem('acm_concurrency_settings')
            setOpenaiKey('')
            setConcurrency(defaultConcurrency)
            notify.success('Reset complete')
          }} className="inline-flex items-center gap-2 px-4 py-2 border rounded-md text-foreground hover:bg-accent transition-colors">
            <RotateCcw className="h-4 w-4" />
            Reset
          </button>
          <button onClick={() => {
            // Save API keys and concurrency settings
            if (openaiKey) {
              localStorage.setItem('acm_api_key', openaiKey)
            }
            localStorage.setItem('acm_concurrency_settings', JSON.stringify(concurrency))
            notify.success('Settings saved')
          }} className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors">
            <Save className="h-4 w-4" />
            Save
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        {[
          { id: 'api', label: 'API Keys', icon: Key },
          { id: 'github', label: 'GitHub', icon: Github },
          { id: 'defaults', label: 'Defaults', icon: Database },
          { id: 'advanced', label: 'Advanced', icon: Zap },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 border-b-2 -mb-px transition-colors',
              activeTab === tab.id
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'api' && (
        <div className="space-y-6">
          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">OpenAI</h2>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                API Key
              </label>
              <input
                type="password"
                placeholder="sk-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="text-xs text-muted-foreground">
                Used for GPT-4 and other OpenAI models
              </p>
            </div>
          </div>

          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">Anthropic</h2>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                API Key
              </label>
              <input
                type="password"
                placeholder="sk-ant-..."
                className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="text-xs text-muted-foreground">
                Used for Claude models
              </p>
            </div>
          </div>

          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">Google</h2>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                API Key
              </label>
              <input
                type="password"
                placeholder="AIza..."
                className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p className="text-xs text-muted-foreground">
                Used for Gemini models
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2 p-4 bg-muted rounded-lg">
            <Info className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Environment Variables</p>
              <p className="mt-1">
                API keys can also be set via environment variables:
                OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
              </p>
            </div>
          </div>
        </div>
      )}

      {/* GitHub Tab */}
      {activeTab === 'github' && (
        <div className="space-y-6">
          {/* Header with Add button */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">GitHub Connections</h2>
              <p className="text-sm text-muted-foreground">
                Connect to GitHub repositories to use as input source or output destination
              </p>
            </div>
            <button
              onClick={() => setShowAddConnection(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Add Connection
            </button>
          </div>

          {/* Add Connection Form */}
          {showAddConnection && (
            <div className="bg-card border rounded-lg p-4 space-y-4">
              <h3 className="font-semibold text-foreground">New GitHub Connection</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Connection Name *</label>
                  <input
                    type="text"
                    placeholder="My Project Repo"
                    value={newConnection.name}
                    onChange={(e) => setNewConnection(prev => ({ ...prev, name: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Repository *</label>
                  <input
                    type="text"
                    placeholder="owner/repo"
                    value={newConnection.repo}
                    onChange={(e) => setNewConnection(prev => ({ ...prev, repo: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p className="text-xs text-muted-foreground">Format: owner/repository-name</p>
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Branch</label>
                  <input
                    type="text"
                    placeholder="main"
                    value={newConnection.branch}
                    onChange={(e) => setNewConnection(prev => ({ ...prev, branch: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Personal Access Token *</label>
                  <input
                    type="password"
                    placeholder="ghp_..."
                    value={newConnection.token}
                    onChange={(e) => setNewConnection(prev => ({ ...prev, token: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p className="text-xs text-muted-foreground">
                    <a 
                      href="https://github.com/settings/tokens/new" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-primary hover:underline inline-flex items-center gap-1"
                    >
                      Create token <ExternalLink className="h-3 w-3" />
                    </a>
                    {' '}— needs repo scope for read/write
                  </p>
                </div>
              </div>
              
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => {
                    setShowAddConnection(false)
                    setNewConnection({ name: '', repo: '', branch: 'main', token: '' })
                  }}
                  className="px-4 py-2 border rounded-md text-foreground hover:bg-accent transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddConnection}
                  disabled={addingConnection}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {addingConnection ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  Add Connection
                </button>
              </div>
            </div>
          )}

          {/* Connections List */}
          {loadingConnections ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : githubConnections.length === 0 ? (
            <div className="bg-card border rounded-lg p-8 text-center">
              <Github className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-semibold text-foreground mb-2">No GitHub Connections</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Add a connection to use GitHub repos as input source or output destination
              </p>
              <button
                onClick={() => setShowAddConnection(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Add Your First Connection
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {githubConnections.map((conn) => (
                <div key={conn.id} className="bg-card border rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <Github className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-foreground">{conn.name}</h3>
                          {conn.is_valid ? (
                            <span className="inline-flex items-center gap-1 text-xs text-green-500">
                              <CheckCircle className="h-3 w-3" /> Valid
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-red-500">
                              <XCircle className="h-3 w-3" /> Invalid
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">{conn.repo} ({conn.branch})</p>
                        {conn.last_tested_at && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Last tested: {new Date(conn.last_tested_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleBrowseConnection(conn.id)}
                        className="p-2 hover:bg-accent rounded-md transition-colors"
                        title="Browse files"
                      >
                        <FolderOpen className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleTestConnection(conn.id)}
                        disabled={testingConnection === conn.id}
                        className="p-2 hover:bg-accent rounded-md transition-colors"
                        title="Test connection"
                      >
                        {testingConnection === conn.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDeleteConnection(conn.id)}
                        className="p-2 hover:bg-red-500/10 text-red-500 rounded-md transition-colors"
                        title="Delete connection"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  
                  {/* Browse Panel */}
                  {browsingConnection === conn.id && (
                    <div className="mt-4 pt-4 border-t">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-foreground">Browse:</span>
                          <code className="text-xs bg-muted px-2 py-1 rounded">{browsePath}</code>
                        </div>
                        <button
                          onClick={() => setBrowsingConnection(null)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          Close
                        </button>
                      </div>
                      
                      {loadingBrowse ? (
                        <div className="flex items-center justify-center py-4">
                          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                        </div>
                      ) : (
                        <div className="bg-muted rounded-md max-h-64 overflow-y-auto">
                          {browsePath !== '/' && (
                            <button
                              onClick={() => {
                                const parentPath = browsePath.split('/').slice(0, -1).join('/') || '/'
                                handleBrowseConnection(conn.id, parentPath)
                              }}
                              className="w-full text-left px-3 py-2 hover:bg-accent/50 flex items-center gap-2 text-sm"
                            >
                              <FolderOpen className="h-4 w-4 text-muted-foreground" />
                              <span>..</span>
                            </button>
                          )}
                          {browseContents.map((item) => (
                            <button
                              key={item.path}
                              onClick={() => {
                                if (item.type === 'dir') {
                                  handleBrowseConnection(conn.id, item.path)
                                }
                              }}
                              className={cn(
                                "w-full text-left px-3 py-2 hover:bg-accent/50 flex items-center gap-2 text-sm",
                                item.type === 'file' && "cursor-default"
                              )}
                            >
                              {item.type === 'dir' ? (
                                <FolderOpen className="h-4 w-4 text-yellow-500" />
                              ) : (
                                <span className="w-4 h-4 flex items-center justify-center text-xs">📄</span>
                              )}
                              <span className={item.type === 'dir' ? 'text-foreground' : 'text-muted-foreground'}>
                                {item.name}
                              </span>
                              {item.size !== null && (
                                <span className="text-xs text-muted-foreground ml-auto">
                                  {item.size > 1024 ? `${(item.size / 1024).toFixed(1)} KB` : `${item.size} B`}
                                </span>
                              )}
                            </button>
                          ))}
                          {browseContents.length === 0 && (
                            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                              Empty directory
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Info about GitHub usage */}
          <div className="flex items-start gap-2 p-4 bg-muted rounded-lg">
            <Info className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="text-sm text-muted-foreground">
              <p className="font-medium text-foreground">How to Use GitHub Connections</p>
              <ul className="mt-2 space-y-1 list-disc list-inside">
                <li>Use as <strong>input source</strong>: Select files from GitHub repos as input documents in Configure</li>
                <li>Use as <strong>output destination</strong>: Push generated documents back to GitHub from run results</li>
                <li>Token needs <code className="bg-background px-1 rounded">repo</code> scope for full read/write access</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'defaults' && (
        <div className="space-y-6">
          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">Default Generator Settings</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Generator Adapter
                </label>
                <select className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
                  <option value="fpf">FilePromptForge (FPF)</option>
                  <option value="gptr">GPT-Researcher</option>
                </select>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Default Model
                </label>
                <select className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="claude-3-opus">Claude 3 Opus</option>
                  <option value="claude-3-sonnet">Claude 3.5 Sonnet</option>
                  <option value="gemini-pro">Gemini Pro</option>
                </select>
              </div>
            </div>
          </div>

          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">Default Evaluator Settings</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Evaluator Model
                </label>
                <select className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="claude-3-sonnet">Claude 3.5 Sonnet</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Scoring Rubric
                </label>
                <select className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring">
                  <option value="default">Default (1-5 scale)</option>
                  <option value="binary">Binary (Pass/Fail)</option>
                  <option value="percentage">Percentage (0-100)</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'advanced' && (
        <div className="space-y-6">
          {/* Info Banner */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-blue-300">Settings Moved to Build Preset</h3>
              <p className="text-sm text-blue-200/70 mt-1">
                Concurrency, timeout, retry, and iteration settings are now configured per-preset on the Build Preset page.
                This ensures all execution settings are saved together with your preset configuration.
              </p>
            </div>
          </div>

          {/* FPF Logging Settings */}
          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">FPF Logging</h2>
            <p className="text-sm text-muted-foreground">
              Configure how FilePromptForge subprocess output is logged.
            </p>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  FPF Log Output
                </label>
                <select 
                  value={concurrency.fpfLogOutput}
                  onChange={(e) => setConcurrency(prev => ({ ...prev, fpfLogOutput: e.target.value as 'stream' | 'file' | 'none' }))}
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="stream">Stream (real-time to console)</option>
                  <option value="file">File (log to disk)</option>
                  <option value="none">None (silent)</option>
                </select>
                <p className="text-xs text-muted-foreground">
                  Where FPF subprocess output is logged
                </p>
              </div>

              {concurrency.fpfLogOutput === 'file' && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    FPF Log File Path
                  </label>
                  <input
                    type="text"
                    value={concurrency.fpfLogFilePath}
                    onChange={(e) => setConcurrency(prev => ({ ...prev, fpfLogFilePath: e.target.value }))}
                    placeholder="logs/{run_id}/fpf_output.log"
                    className="w-full px-3 py-2 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <p className="text-xs text-muted-foreground">
                    Use {'{run_id}'} as placeholder for run identifier
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Data Storage */}
          <div className="bg-card border rounded-lg p-4 space-y-4">
            <h2 className="font-semibold text-foreground">Data Storage</h2>
            <p className="text-sm text-muted-foreground">
              Read-only paths showing where ACM stores data.
            </p>
            
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Database Path
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  defaultValue="~/.acm2/acm2.db"
                  className="flex-1 px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  readOnly
                />
                <button className="px-4 py-2 border rounded-md text-foreground hover:bg-accent transition-colors">
                  Browse
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Reports Directory
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  defaultValue="~/.acm2/reports"
                  className="flex-1 px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  readOnly
                />
                <button className="px-4 py-2 border rounded-md text-foreground hover:bg-accent transition-colors">
                  Browse
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
