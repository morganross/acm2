import { useEffect, useMemo, useState } from 'react'
import { Section } from '../ui/section'
import { Slider } from '../ui/slider'
import { Checkbox, CheckboxGroup } from '../ui/checkbox'
import { FileText, Cpu, Zap, RefreshCw, ChevronDown, ChevronRight, Gift } from 'lucide-react'
import { useConfigStore } from '../../stores/config'
import { useModelCatalog } from '../../stores/modelCatalog'

export function FpfParamsPanel() {
  const config = useConfigStore()
  const { fpfModels, fpfFreeModels, models, isLoading, fetchModels } = useModelCatalog()
  const [freeModelsExpanded, setFreeModelsExpanded] = useState(false)

  // Fetch models on mount if empty
  useEffect(() => {
    if (fpfModels.length === 0) {
      fetchModels()
    }
  }, [])

  // Compute max output tokens based on selected models (use minimum across all selected)
  const maxOutputTokensLimit = useMemo(() => {
    if (config.fpf.selectedModels.length === 0) {
      return 200000 // Default max when no models selected
    }
    const limits = config.fpf.selectedModels
      .map(m => models[m]?.max_output_tokens)
      .filter((limit): limit is number => limit !== null && limit !== undefined)
    
    if (limits.length === 0) {
      return 200000 // Default if no limits found
    }
    return Math.min(...limits)
  }, [config.fpf.selectedModels, models])

  return (
    <Section
      title="FilePromptForge (FPF) Parameters"
      icon={<FileText className="w-5 h-5" />}
      defaultExpanded={true}
    >
      <CheckboxGroup
        title="Enable FilePromptForge"
        enabled={config.fpf.enabled}
        onEnabledChange={(enabled) => config.updateFpf({ enabled })}
      >
        {/* Model Selection */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
            <Cpu className="w-4 h-4" /> Model Selection
            <button 
              onClick={() => fetchModels()}
              disabled={isLoading}
              className="ml-auto text-xs text-gray-500 hover:text-gray-300"
              title="Refresh models from FPF"
            >
              <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </h4>
          <div className="grid grid-cols-2 gap-2" data-section="fpf-models">
            {fpfModels.map((model) => (
              <Checkbox
                key={model}
                checked={config.fpf.selectedModels.includes(model)}
                onChange={(checked) => {
                  const selectedModels = checked
                    ? [...config.fpf.selectedModels, model]
                    : config.fpf.selectedModels.filter((m) => m !== model)
                  config.updateFpf({ selectedModels })
                }}
                label={model}
                dataTestId={`fpf-model-${model}`}
              />
            ))}
          </div>
        </div>

        {/* OpenRouter FREE Models - Collapsible Section */}
        {fpfFreeModels.length > 0 && (
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
                {fpfFreeModels.filter(m => config.fpf.selectedModels.includes(m)).length} / {fpfFreeModels.length} selected
              </span>
            </button>
            {freeModelsExpanded && (
              <div className="p-3 bg-gray-800/50">
                <p className="text-xs text-gray-400 mb-3">
                  $0/M tokens - Community-provided free endpoints with rate limits
                </p>
                <div className="grid grid-cols-2 gap-2" data-section="fpf-free-models">
                  {fpfFreeModels.map((model) => (
                    <Checkbox
                      key={model}
                      checked={config.fpf.selectedModels.includes(model)}
                      onChange={(checked) => {
                        const selectedModels = checked
                          ? [...config.fpf.selectedModels, model]
                          : config.fpf.selectedModels.filter((m) => m !== model)
                        config.updateFpf({ selectedModels })
                      }}
                      label={model.replace('openrouter:', '').replace(':free', ' 🆓')}
                      dataTestId={`fpf-model-${model}`}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Parameter Sliders */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Zap className="w-4 h-4" /> Generation Parameters
          </h4>

          <Slider
            label="Temperature"
            value={config.fpf.temperature}
            onChange={(val) => config.updateFpf({ temperature: val })}
            min={0}
            max={2}
            step={0.1}
            displayValue={config.fpf.temperature.toFixed(1)}
          />

          <Slider
            label="Max Output Tokens"
            value={Math.min(config.fpf.maxTokens, maxOutputTokensLimit)}
            onChange={(val) => config.updateFpf({ maxTokens: val })}
            min={512}
            max={maxOutputTokensLimit}
            step={256}
            displayValue={`${config.fpf.maxTokens.toLocaleString()} (limit: ${maxOutputTokensLimit.toLocaleString()})`}
          />

          <Slider
            label="Thinking Budget (tokens)"
            value={config.fpf.thinkingBudget}
            onChange={(val) => config.updateFpf({ thinkingBudget: val })}
            min={256}
            max={200000}
            step={256}
            displayValue={config.fpf.thinkingBudget}
          />
        </div>
      </CheckboxGroup>
    </Section>
  )
}
