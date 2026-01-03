import { Section } from '../ui/section'
import { Slider } from '../ui/slider'
import { Checkbox } from '../ui/checkbox'
import { Select } from '../ui/select'
import { Settings, FolderOpen, ScrollText, Target } from 'lucide-react'
import { useConfigStore } from '../../stores/config'

export function GeneralPanel() {
  const config = useConfigStore()

  return (
    <Section
      title="General Settings"
      icon={<Settings className="w-5 h-5" />}
      defaultExpanded={true}
    >
      <div className="space-y-4">
        {/* Main Run Settings */}
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Settings className="w-4 h-4" /> Run Configuration
          </h4>

          <Slider
            label="Total Iterations"
            value={config.general.iterations}
            onChange={(val) => config.updateGeneral({ iterations: val })}
            min={1}
            max={9}
            step={1}
            displayValue={`${config.general.iterations} iterations`}
          />
        </div>

        {/* Generation Quality Settings */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Target className="w-4 h-4" /> Generation Quality
          </h4>

          <Checkbox
            checked={config.general.exposeCriteriaToGenerators}
            onChange={(val) => config.updateGeneral({ exposeCriteriaToGenerators: val })}
            label="Expose Evaluation Criteria to Generators"
          />
          <p className="text-xs text-gray-500 ml-6">
            When enabled, generators will see the evaluation criteria they'll be judged on, 
            helping them optimize output quality.
          </p>
        </div>

        {/* Output Settings */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <FolderOpen className="w-4 h-4" /> Output Settings
          </h4>

          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-400">Output Directory</label>
            <input
              type="text"
              value={config.general.outputDir}
              onChange={(e) => config.updateGeneral({ outputDir: e.target.value })}
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="./output"
            />
          </div>

          <Checkbox
            checked={config.general.saveIntermediate}
            onChange={(val) => config.updateGeneral({ saveIntermediate: val })}
            label="Save Intermediate Results"
          />
        </div>

        {/* Logging Settings */}
        <div className="space-y-3 border-t border-gray-700 pt-4">
          <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <ScrollText className="w-4 h-4" /> Logging
          </h4>

          <Checkbox
            checked={config.general.enableLogging}
            onChange={(val) => config.updateGeneral({ enableLogging: val })}
            label="Enable Logging"
          />

          <Select
            label="Log Level"
            value={config.general.logLevel}
            onChange={(val) => config.updateGeneral({ logLevel: val })}
            options={[
              { value: 'ERROR', label: 'Error' },
              { value: 'WARNING', label: 'Warning' },
              { value: 'INFO', label: 'Info' },
              { value: 'DEBUG', label: 'Debug' },
              { value: 'VERBOSE', label: 'Verbose (captures FPF output)' },
            ]}
          />
        </div>
      </div>
    </Section>
  )
}
