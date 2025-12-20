import { Section } from '../ui/section'
import { Slider } from '../ui/slider'
import { Checkbox } from '../ui/checkbox'
import { Zap, Clock, RefreshCw } from 'lucide-react'
import { useConfigStore } from '../../stores/config'

export function ConcurrencyPanel() {
  const config = useConfigStore()

  return (
    <Section
      title="Concurrency & Rate Limiting"
      icon={<Zap className="w-5 h-5" />}
      defaultExpanded={true}
    >
      {/* Main Concurrency Sliders */}
      <div className="space-y-4">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Zap className="w-4 h-4" /> Concurrency Settings
          </h4>

          <Slider
            label="Max Concurrent Requests"
            value={config.concurrency.maxConcurrent}
            onChange={(val) => config.updateConcurrency({ maxConcurrent: val })}
            min={1}
            max={20}
            step={1}
            displayValue={`${config.concurrency.maxConcurrent} concurrent`}
          />

          <Slider
            label="Launch Delay (seconds)"
            value={config.concurrency.launchDelay}
            onChange={(val) => config.updateConcurrency({ launchDelay: val })}
            min={0.1}
            max={5.0}
            step={0.1}
            displayValue={`${config.concurrency.launchDelay.toFixed(1)}s`}
          />
        </div>

        {/* Rate Limiting */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Rate Limiting
          </h4>

          <Checkbox
            checked={config.concurrency.enableRateLimiting}
            onChange={(val) => config.updateConcurrency({ enableRateLimiting: val })}
            label="Enable Rate Limiting"
          />
        </div>

        {/* Retry Settings */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <RefreshCw className="w-4 h-4" /> Retry Settings
          </h4>

          <Slider
            label="Max Retries"
            value={config.concurrency.maxRetries}
            onChange={(val) => config.updateConcurrency({ maxRetries: val })}
            min={0}
            max={10}
            step={1}
            displayValue={`${config.concurrency.maxRetries} retries`}
          />

          <Slider
            label="Retry Delay (seconds)"
            value={config.concurrency.retryDelay}
            onChange={(val) => config.updateConcurrency({ retryDelay: val })}
            min={0.5}
            max={10.0}
            step={0.5}
            displayValue={`${config.concurrency.retryDelay.toFixed(1)}s`}
          />
        </div>
      </div>
    </Section>
  )
}
