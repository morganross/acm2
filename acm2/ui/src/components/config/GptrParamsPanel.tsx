import { useEffect } from 'react'
import { Section } from '../ui/section'
import { Slider } from '../ui/slider'
import { Checkbox, CheckboxGroup } from '../ui/checkbox'
import { Settings, Cpu, Zap } from 'lucide-react'
import { useConfigStore } from '../../stores/config'
import { useModelCatalog } from '../../stores/modelCatalog'

export function GptrParamsPanel() {
  const config = useConfigStore()
  const { gptrModels, fetchModels } = useModelCatalog()

  useEffect(() => {
    if (gptrModels.length === 0) {
      fetchModels()
    }
  }, [])

  return (
    <Section
      title="GPT-Researcher (GPTR) Parameters"
      icon={<Settings className="w-5 h-5" />}
      defaultExpanded={true}
    >
      {/* Enable/Disable Toggle */}
      <CheckboxGroup
        title="Enable GPT-Researcher"
        enabled={config.gptr.enabled}
        onEnabledChange={(enabled) => config.updateGptr({ enabled })}
      >
        {/* Model Selection */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
            <Cpu className="w-4 h-4" /> Model Selection
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {gptrModels.map((model) => (
              <Checkbox
                key={model}
                checked={config.gptr.selectedModels.includes(model)}
                onChange={(checked) => {
                  const models = checked
                    ? [...config.gptr.selectedModels, model]
                    : config.gptr.selectedModels.filter((m: string) => m !== model)
                  config.updateGptr({ selectedModels: models })
                }}
                label={model}
              />
            ))}
          </div>
        </div>

        {/* Token Limits Section */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Zap className="w-4 h-4" /> Token Limits
          </h4>
          
          <Slider
            label="Fast LLM Token Limit"
            value={config.gptr.fastLlmTokenLimit}
            onChange={(val) => config.updateGptr({ fastLlmTokenLimit: val })}
            min={1000}
            max={32000}
            step={1000}
            displayValue={`${config.gptr.fastLlmTokenLimit.toLocaleString()} tokens`}
          />

          <Slider
            label="Smart LLM Token Limit"
            value={config.gptr.smartLlmTokenLimit}
            onChange={(val) => config.updateGptr({ smartLlmTokenLimit: val })}
            min={1000}
            max={128000}
            step={1000}
            displayValue={`${config.gptr.smartLlmTokenLimit.toLocaleString()} tokens`}
          />

          <Slider
            label="Strategic LLM Token Limit"
            value={config.gptr.strategicLlmTokenLimit}
            onChange={(val) => config.updateGptr({ strategicLlmTokenLimit: val })}
            min={1000}
            max={200000}
            step={1000}
            displayValue={`${config.gptr.strategicLlmTokenLimit.toLocaleString()} tokens`}
          />

          <Slider
            label="Browse Chunk Max Length"
            value={config.gptr.browseChunkMaxLength}
            onChange={(val) => config.updateGptr({ browseChunkMaxLength: val })}
            min={1000}
            max={20000}
            step={500}
            displayValue={`${config.gptr.browseChunkMaxLength.toLocaleString()} chars`}
          />
        </div>
      </CheckboxGroup>
    </Section>
  )
}
