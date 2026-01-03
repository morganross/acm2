import { useEffect, useState } from 'react'
import { Section } from '../ui/section'
import { Slider } from '../ui/slider'
import { Checkbox, CheckboxGroup } from '../ui/checkbox'
import { Network, Cpu, GitBranch, Settings, Clock, Gift, ChevronDown, ChevronRight } from 'lucide-react'
import { useConfigStore } from '../../stores/config'
import { useModelCatalog } from '../../stores/modelCatalog'

export function DeepResearchPanel() {
  const config = useConfigStore()
  const { drModels, drFreeModels, fetchModels } = useModelCatalog()
  const [freeModelsExpanded, setFreeModelsExpanded] = useState(false)

  useEffect(() => {
    if (drModels.length === 0) {
      fetchModels()
    }
  }, [])

  return (
    <Section
      title="Deep Research (DR) Parameters"
      icon={<Network className="w-5 h-5" />}
      defaultExpanded={true}
    >
      <CheckboxGroup
        title="Enable Deep Research"
        enabled={config.dr.enabled}
        onEnabledChange={(enabled) => config.updateDr({ enabled })}
      >
        {/* Model Selection */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
            <Cpu className="w-4 h-4" /> Model Selection
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {drModels.map((model) => (
              <Checkbox
                key={model}
                checked={config.dr.selectedModels.includes(model)}
                onChange={(checked) => {
                  const models = checked
                    ? [...config.dr.selectedModels, model]
                    : config.dr.selectedModels.filter((m: string) => m !== model)
                  config.updateDr({ selectedModels: models })
                }}
                label={model}
              />
            ))}
          </div>
        </div>

        {/* OpenRouter FREE Models - Collapsible Section */}
        {drFreeModels.length > 0 && (
          <div className="mb-4 border border-green-700/50 rounded-lg overflow-hidden">
            <button
              onClick={() => setFreeModelsExpanded(!freeModelsExpanded)}
              className="w-full flex items-center gap-2 px-3 py-2 bg-green-900/30 hover:bg-green-900/50 transition-colors text-left"
            >
              {freeModelsExpanded ? (
                <ChevronDown className="w-4 h-4 text-green-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-green-400" />
              )}
              <Gift className="w-4 h-4 text-green-400" />
              <span className="text-sm font-semibold text-green-300">
                OpenRouter FREE Models
              </span>
              <span className="ml-auto text-xs text-green-500">
                {drFreeModels.filter(m => config.dr.selectedModels.includes(m)).length} / {drFreeModels.length} selected
              </span>
            </button>
            {freeModelsExpanded && (
              <div className="p-3 bg-gray-800/50">
                <p className="text-xs text-gray-400 mb-3">
                  $0/M tokens - Community-provided free endpoints with rate limits
                </p>
                <div className="grid grid-cols-2 gap-2" data-section="dr-free-models">
                  {drFreeModels.map((model) => (
                    <Checkbox
                      key={model}
                      checked={config.dr.selectedModels.includes(model)}
                      onChange={(checked) => {
                        const models = checked
                          ? [...config.dr.selectedModels, model]
                          : config.dr.selectedModels.filter((m: string) => m !== model)
                        config.updateDr({ selectedModels: models })
                      }}
                      label={model.replace('openrouter:', '').replace(':free', ' 🆓')}
                      dataTestId={`dr-model-${model}`}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Search Tree Parameters */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <GitBranch className="w-4 h-4" /> Search Tree Parameters
          </h4>

          <Slider
            label="Breadth (Topics per Level)"
            value={config.dr.breadth}
            onChange={(val) => config.updateDr({ breadth: val })}
            min={1}
            max={8}
            step={1}
            displayValue={`${config.dr.breadth} topics`}
          />

          <Slider
            label="Depth (Search Levels)"
            value={config.dr.depth}
            onChange={(val) => config.updateDr({ depth: val })}
            min={1}
            max={8}
            step={1}
            displayValue={`${config.dr.depth} levels`}
          />

          <Slider
            label="Max Results per Search"
            value={config.dr.maxResults}
            onChange={(val) => config.updateDr({ maxResults: val })}
            min={1}
            max={20}
            step={1}
            displayValue={`${config.dr.maxResults} results`}
          />

          <Slider
            label="Concurrency Limit"
            value={config.dr.concurrencyLimit}
            onChange={(val) => config.updateDr({ concurrencyLimit: val })}
            min={1}
            max={10}
            step={1}
            displayValue={`${config.dr.concurrencyLimit} concurrent`}
          />
        </div>

        {/* Log Level Section */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Settings className="w-4 h-4" /> Logging
          </h4>
          
          <div>
            <label className="text-sm font-medium text-gray-300 mb-2 block">
              Log Level
            </label>
            <select
              value={config.dr.logLevel}
              onChange={(e) => config.updateDr({ logLevel: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="DEBUG">DEBUG - Most verbose</option>
              <option value="INFO">INFO - Standard</option>
              <option value="WARNING">WARNING - Warnings only</option>
              <option value="ERROR">ERROR - Errors only</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Controls Deep Research subprocess logging verbosity
            </p>
          </div>
        </div>

        {/* Timeout & Retry Section */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Timeout & Retry
          </h4>
          
          <Slider
            label="Subprocess Timeout"
            value={config.dr.subprocessTimeoutMinutes}
            onChange={(val) => config.updateDr({ subprocessTimeoutMinutes: val })}
            min={10}
            max={45}
            step={5}
            displayValue={`${config.dr.subprocessTimeoutMinutes} minutes`}
          />
          <p className="text-xs text-gray-500 -mt-2">
            Kill hung Deep Research subprocess after this time (10-45 min)
          </p>

          <Slider
            label="Timeout Retries"
            value={config.dr.subprocessRetries}
            onChange={(val) => config.updateDr({ subprocessRetries: val })}
            min={0}
            max={3}
            step={1}
            displayValue={`${config.dr.subprocessRetries} ${config.dr.subprocessRetries === 1 ? 'retry' : 'retries'}`}
          />
          <p className="text-xs text-gray-500 -mt-2">
            Retry on timeout before marking as failed (0-3)
          </p>
        </div>
      </CheckboxGroup>
    </Section>
  )
}
