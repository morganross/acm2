import { useState } from 'react'
import { Save, RotateCcw, Key, Database, Zap, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { notify } from '@/stores/notifications'

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
  const [activeTab, setActiveTab] = useState<'api' | 'defaults' | 'advanced'>('api')
  const [openaiKey, setOpenaiKey] = useState(localStorage.getItem('acm_api_key') || '')
  const [concurrency, setConcurrency] = useState<ConcurrencySettings>(loadConcurrencySettings)

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
