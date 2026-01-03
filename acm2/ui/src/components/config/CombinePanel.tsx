import { useEffect, useState, useMemo } from 'react'
import { Section } from '../ui/section'
import { Checkbox, CheckboxGroup } from '../ui/checkbox'
import { Combine as CombineIcon, Cpu, FileText, ExternalLink, Scale, Sliders, Gift, ChevronDown, ChevronRight } from 'lucide-react'
import { useConfigStore } from '../../stores/config'
import { useModelCatalog } from '../../stores/modelCatalog'
import { contentsApi, type ContentSummary } from '../../api/contents'

export function CombinePanel() {
  const config = useConfigStore()
  const { combineModels, combineFreeModels, models, fetchModels } = useModelCatalog()
  const [freeModelsExpanded, setFreeModelsExpanded] = useState(false)
  
  // Content Library items for combine instructions
  const [combineInstructionContents, setCombineInstructionContents] = useState<ContentSummary[]>([])

  useEffect(() => {
    if (combineModels.length === 0) {
      fetchModels()
    }
    // Fetch content library items for combine instructions
    const loadContents = async () => {
      try {
        const result = await contentsApi.list({ content_type: 'combine_instructions' })
        setCombineInstructionContents(result.items)
      } catch (err) {
        console.error('Failed to load combine instruction contents:', err)
      }
    }
    loadContents()
  }, [])

  // Compute max output tokens based on selected combine models (use minimum across all selected)
  const maxOutputTokensLimit = useMemo(() => {
    if (config.combine.selectedModels.length === 0) {
      return 128000 // Default max when no models selected
    }
    const limits = config.combine.selectedModels
      .map(m => models[m]?.max_output_tokens)
      .filter((limit): limit is number => limit !== null && limit !== undefined)
    
    if (limits.length === 0) {
      return 128000 // Default if no limits found
    }
    return Math.min(...limits)
  }, [config.combine.selectedModels, models])

  return (
    <Section
      title="Combine (Gold Standard)"
      icon={<CombineIcon className="w-5 h-5" />}
      defaultExpanded={true}
    >
      <CheckboxGroup
        title="Enable Combine"
        enabled={config.combine.enabled}
        onEnabledChange={(enabled) => config.updateCombine({ enabled })}
      >
        {/* Description */}
        <p style={{ fontSize: '13px', color: '#9ca3af', marginBottom: '12px' }}>
          Takes the top 2 evaluated reports and combines them into a "Gold Standard" report using the selected model(s).
        </p>

        {/* Model Selection */}
        <div data-section="combine-models">
          <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
            <Cpu className="w-4 h-4" /> Combine Model
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {combineModels.map((model) => (
              <Checkbox
                key={model}
                checked={config.combine.selectedModels.includes(model)}
                onChange={(checked) => {
                  const models = checked
                    ? [...config.combine.selectedModels, model]
                    : config.combine.selectedModels.filter((m: string) => m !== model)
                  config.updateCombine({ selectedModels: models })
                }}
                label={model}
                dataTestId={`combine-model-${model}`}
              />
            ))}
          </div>
          
          {/* OpenRouter FREE Models - Collapsible */}
          {combineFreeModels.length > 0 && (
            <div className="mt-3 border border-green-700 rounded-lg overflow-hidden" data-section="combine-free-models">
              <button
                onClick={() => setFreeModelsExpanded(!freeModelsExpanded)}
                className="w-full flex items-center justify-between p-2 bg-green-900/30 hover:bg-green-900/50 transition-colors"
              >
                <div className="flex items-center gap-2 text-green-400">
                  <Gift className="w-4 h-4" />
                  <span className="text-sm font-medium">OpenRouter FREE Models</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-green-500">
                    {config.combine.selectedModels.filter((m: string) => combineFreeModels.includes(m)).length} / {combineFreeModels.length} selected
                  </span>
                  {freeModelsExpanded ? (
                    <ChevronDown className="w-4 h-4 text-green-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-green-400" />
                  )}
                </div>
              </button>
              {freeModelsExpanded && (
                <div className="p-3 bg-gray-800/50">
                  <div className="grid grid-cols-2 gap-2">
                    {combineFreeModels.map((model) => (
                      <Checkbox
                        key={model}
                        checked={config.combine.selectedModels.includes(model)}
                        onChange={(checked) => {
                          const models = checked
                            ? [...config.combine.selectedModels, model]
                            : config.combine.selectedModels.filter((m: string) => m !== model)
                          config.updateCombine({ selectedModels: models })
                        }}
                        label={`🆓 ${model}`}
                        dataTestId={`combine-model-${model}`}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Max Tokens Slider */}
        <div className="border-t border-gray-700 pt-4 mt-4" data-section="combine-max-tokens">
          <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
            <Sliders className="w-4 h-4" /> Max Output Tokens
          </h4>
          <p className="text-xs text-gray-500 mb-2">
            Maximum tokens for the combine model output (includes reasoning tokens for reasoning models). Limit: {maxOutputTokensLimit.toLocaleString()}
          </p>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="4000"
              max={maxOutputTokensLimit}
              step="1000"
              value={Math.min(config.combine.maxTokens, maxOutputTokensLimit)}
              onChange={(e) => config.updateCombine({ maxTokens: parseInt(e.target.value) })}
              className="flex-1"
            />
            <span className="text-sm text-gray-300 w-20 text-right">{config.combine.maxTokens.toLocaleString()}</span>
          </div>
        </div>

        {/* Combine Instructions */}
        <div className="space-y-2 border-t border-gray-700 pt-4 mt-4" data-section="combine-instructions">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
              <FileText className="w-4 h-4" /> Combine Instructions
            </h4>
            <a 
              href="/content" 
              target="_blank"
              className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              Library
            </a>
          </div>
          <p className="text-xs text-gray-500 mb-2">
            Custom instructions for combining top reports into a Gold Standard document.
          </p>
          {combineInstructionContents.length === 0 ? (
            <p className="text-xs text-gray-500">No combine instructions in library. <a href="/content" className="text-purple-400 hover:text-purple-300">Create one →</a></p>
          ) : (
            <select
              value={config.combine.combineInstructionsId || ''}
              onChange={(e) => config.updateCombine({ combineInstructionsId: e.target.value || null })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">-- Use Default --</option>
              {combineInstructionContents.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}
        </div>

        {/* Post-Combine Evaluation Info */}
        <div className="border-t border-gray-700 pt-4 mt-4" data-section="post-combine-eval">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Scale className="w-4 h-4" />
            <span>Post-combine evaluation runs automatically when combine produces documents</span>
          </div>
        </div>
      </CheckboxGroup>
    </Section>
  )
}
