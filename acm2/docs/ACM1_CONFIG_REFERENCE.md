# ACM 1.0 Configuration Reference

This document describes all configuration files and GUI elements in ACM 1.0. ACM 2.0 must support **at least** this level of configurability through its API and web GUI.

---

## 1. Configuration Files Overview

| File | Location | Format | Purpose |
|------|----------|--------|---------|
| `config.yaml` | `api_cost_multiplier/` | YAML | Main runtime configuration |
| `presets.yaml` | `api_cost_multiplier/` | YAML | Named preset configurations (e.g., "low", "888") |
| `fpf_config.yaml` | `FilePromptForge/` | YAML | FPF-specific settings |
| `default.py` | `gpt-researcher/.../config/variables/` | Python | GPT-Researcher defaults |
| `task.json` | `gpt-researcher/multi_agents/` | JSON | Multi-Agent task configuration |
| Provider YAMLs | `model_registry/providers/` | YAML | Model definitions per provider |
| `ma_supported.yaml` | `model_registry/` | YAML | Allowlist of MA-compatible models |

---

## 2. config.yaml – Main Configuration

### 2.1 Path Settings

```yaml
input_folder: C:\dev\invade\firstpub-Platform\docs\...
output_folder: C:\dev\invade\firstpub-Platform\docs\...\outputs\dealbarb2
instructions_file: C:\dev\invade\...\Eo instructions.md
guidelines_file: c:\dev\silky\guidelines.md
```

| Field | Type | Description |
|-------|------|-------------|
| `input_folder` | string (path) | Directory containing input markdown files |
| `output_folder` | string (path) | Directory for generated artifacts |
| `instructions_file` | string (path) | Markdown file with generation instructions |
| `guidelines_file` | string (path) | Optional file with report guidelines |

### 2.2 Run Configuration

```yaml
one_file_only: true
iterations_default: 2
runs:
  - type: fpf
    provider: openai
    model: gpt-5.1
  - type: dr
    provider: openai
    model: gpt-5.1
```

| Field | Type | Description |
|-------|------|-------------|
| `one_file_only` | boolean | Process only the first file in input folder |
| `iterations_default` | integer (1-8+) | Number of iterations per document per generator |
| `runs` | array | List of generator configurations to execute |
| `runs[].type` | enum | Generator type: `fpf`, `gptr`, `dr` |
| `runs[].provider` | string | LLM provider: `openai`, `google`, `anthropic`, `openrouter` |
| `runs[].model` | string | Model name (e.g., `gpt-5.1`, `gemini-2.5-flash`) |

### 2.3 Concurrency Settings

```yaml
concurrency:
  gpt_researcher:
    enabled: true
    max_concurrent_reports: 11
    launch_delay_seconds: 0.5
  multi_agent:
    enabled: true
    max_concurrent_runs: 4
    launch_delay_seconds: 0.5

policies:
  concurrency:
    gpt_researcher:
      enforce: false
      max_concurrent_reports_cap: 11
      launch_delay_seconds_min: 0.5
```

| Field | Type | Description |
|-------|------|-------------|
| `concurrency.gpt_researcher.enabled` | boolean | Enable GPT-R concurrency |
| `concurrency.gpt_researcher.max_concurrent_reports` | integer | Max parallel GPT-R executions |
| `concurrency.gpt_researcher.launch_delay_seconds` | float | Delay between launches |
| `concurrency.multi_agent.enabled` | boolean | Enable MA concurrency |
| `concurrency.multi_agent.max_concurrent_runs` | integer | Max parallel MA executions |
| `policies.concurrency.*.enforce` | boolean | Whether to enforce caps |

### 2.4 ACM Logging Settings

```yaml
acm:
  log:
    forward_subprocess_output: false
```

| Field | Type | Description |
|-------|------|-------------|
| `acm.log.forward_subprocess_output` | boolean | Forward subprocess stdout to main log |

### 2.5 Evaluation Settings

```yaml
eval:
  log:
    console_level: high
    file_level: Medium
  output_directory: gptr-eval-process/final_reports
  export_directory: gptr-eval-process/exports
  auto_run: true
  iterations: 1
  pairwise_top_n: 3
  mode: both
  judges:
    - provider: google
      model: gemini-2.5-flash
    - provider: google
      model: gemini-3-pro-preview
    - provider: openai
      model: gpt-5
```

| Field | Type | Description |
|-------|------|-------------|
| `eval.log.console_level` | enum | Logging verbosity to console: `low`, `medium`, `high` |
| `eval.log.file_level` | enum | Logging verbosity to file: `low`, `medium`, `high` |
| `eval.output_directory` | string (path) | Directory for evaluation reports |
| `eval.export_directory` | string (path) | Directory for exported evaluation data |
| `eval.auto_run` | boolean | Automatically execute evaluation after generation |
| `eval.iterations` | integer | Number of evaluation iterations |
| `eval.pairwise_top_n` | integer | Top N artifacts to include in pairwise comparison |
| `eval.mode` | enum | Evaluation mode: `single`, `pairwise`, `both` |
| `eval.judges` | array | List of LLM judges for evaluation |
| `eval.judges[].provider` | string | Judge provider |
| `eval.judges[].model` | string | Judge model |

### 2.6 Combine & Revise Settings

```yaml
combine:
  enabled: true
  models:
    - provider: openai
      model: gpt-5.1
```

| Field | Type | Description |
|-------|------|-------------|
| `combine.enabled` | boolean | Enable the Combine Phase |
| `combine.models` | array | Models to use for combining/revising |

---

## 3. presets.yaml – Named Presets

Presets are named configuration bundles that can be loaded to quickly switch between different quality/cost profiles.

### 3.1 Preset Structure

```yaml
low:
  iterations_default: 1
  input_folder: C:/dev/silky/api_cost_multiplier/test/mdinputs/commerce
  output_folder: C:/dev/silky/api_cost_multiplier/test/mdoutputs
  instructions_file: C:/dev/silky/api_cost_multiplier/test/instructions.txt
  guidelines_file: test/report must be in spanish.txt
  follow_guidelines: false
  
  # FPF-specific overrides
  fpf:
    grounding.max_results: 1
    google.max_tokens: 50000
    reasoning.effort: low
    web_search.search_context_size: low
  
  # GPT-Researcher parameters
  FAST_TOKEN_LIMIT: 3000
  SMART_TOKEN_LIMIT: 6000
  STRATEGIC_TOKEN_LIMIT: 4000
  BROWSE_CHUNK_MAX_LENGTH: 8192
  SUMMARY_TOKEN_LIMIT: 700
  TEMPERATURE: 0.4
  MAX_SEARCH_RESULTS_PER_QUERY: 1
  TOTAL_WORDS: 1200
  MAX_ITERATIONS: 1
  MAX_SUBTOPICS: 1
  DEEP_RESEARCH_BREADTH: 1
  DEEP_RESEARCH_DEPTH: 1
  
  # MA parameters
  ma:
    max_sections: 1
  
  # Feature enables
  enable:
    evaluation: true
    pairwise: true
    gptr: true
    dr: true
    ma: true
  
  # Run definitions
  runs:
    - type: fpf
      provider: google
      model: gemini-2.5-flash
    - type: gptr
      provider: openai
      model: gpt-4.1-nano
    # ... more runs
```

### 3.2 Preset Fields Summary

| Category | Fields | Description |
|----------|--------|-------------|
| **Paths** | `input_folder`, `output_folder`, `instructions_file`, `guidelines_file` | Override default paths |
| **General** | `iterations_default`, `follow_guidelines` | Basic execution settings |
| **FPF** | `fpf.*` | FPF-specific parameters |
| **GPT-R** | `FAST_TOKEN_LIMIT`, `SMART_TOKEN_LIMIT`, etc. | GPT-Researcher token/search limits |
| **Temperature** | `TEMPERATURE` | LLM temperature (0.0-1.0) |
| **Research Depth** | `MAX_ITERATIONS`, `MAX_SUBTOPICS`, `DEEP_RESEARCH_BREADTH`, `DEEP_RESEARCH_DEPTH` | Research thoroughness |
| **MA** | `ma.max_sections` | Multi-Agent section limit |
| **Enables** | `enable.fpf`, `enable.gptr`, `enable.dr`, `enable.ma`, `enable.evaluation`, `enable.pairwise` | Toggle generators/features |
| **Runs** | `runs[]` | Complete run definitions |

---

## 4. FPF Configuration (fpf_config.yaml)

### 4.1 Key FPF Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `grounding.max_results` | integer | Max grounding search results |
| `google.max_tokens` | integer | Max tokens for Google models |
| `reasoning.effort` | enum | Reasoning effort: `low`, `medium`, `high` |
| `web_search.search_context_size` | enum | Search context: `low`, `medium`, `high` |

### 4.2 Provider Discovery

FPF providers are discovered dynamically from `FilePromptForge/providers/*.yaml`. Each provider YAML defines:
- Available models
- API parameters
- Token limits
- Provider-specific quirks

---

## 5. GPT-Researcher Configuration (default.py)

### 5.1 Token Limits

| Parameter | Default Range | Description |
|-----------|--------------|-------------|
| `FAST_TOKEN_LIMIT` | 3000-87538 | Token limit for fast operations |
| `SMART_TOKEN_LIMIT` | 6000-175038 | Token limit for smart operations |
| `STRATEGIC_TOKEN_LIMIT` | 4000-87538 | Token limit for strategic operations |
| `BROWSE_CHUNK_MAX_LENGTH` | 8192-26262 | Max chunk length for browsing |
| `SUMMARY_TOKEN_LIMIT` | 700-1759 | Token limit for summaries |

### 5.2 Research Parameters

| Parameter | Range | Description |
|-----------|-------|-------------|
| `TEMPERATURE` | 0.0-1.0 | LLM temperature |
| `MAX_SEARCH_RESULTS_PER_QUERY` | 1-8 | Search results per query |
| `TOTAL_WORDS` | 1200-43762 | Target total words in report |
| `MAX_ITERATIONS` | 1-8 | Max research iterations |
| `MAX_SUBTOPICS` | 1-9 | Max subtopics to explore |
| `DEEP_RESEARCH_BREADTH` | 1-8 | Breadth of deep research |
| `DEEP_RESEARCH_DEPTH` | 1-8 | Depth of deep research |

### 5.3 Model Configuration

| Parameter | Description |
|-----------|-------------|
| `SMART_LLM` | Model for smart/complex tasks |
| `STRATEGIC_LLM` | Model for strategic planning |
| `FAST_LLM` | Model for quick operations |

---

## 6. Model Registry

### 6.1 Provider YAML Structure (e.g., openai.yaml)

```yaml
openai:
  gpt-5:
    provider_name: openai
    model_name: gpt-5
    api_params:
      max_tokens: max_completion_tokens
    context_window: 400000
    quirks:
      - Registration is required for access.
      - 'Input: 272k tokens, Output: 128k tokens.'
    api_version_compatibility: '2025-08-07'
```

### 6.2 Fields Per Model

| Field | Type | Description |
|-------|------|-------------|
| `provider_name` | string | Provider identifier |
| `model_name` | string | Model identifier |
| `api_params` | object | Provider-specific API parameter mappings |
| `context_window` | integer | Max context window in tokens |
| `quirks` | array | Model-specific notes/limitations |
| `api_version_compatibility` | string | Minimum API version |

### 6.3 MA Supported Models (ma_supported.yaml)

```yaml
ma_supported:
  - openai:gpt-4o
  - openai:gpt-4o-mini
  - openai:gpt-4.1
  - openai:gpt-4.1-mini
  - openai:gpt-4.1-nano
  - openai:o4-mini
```

Allowlist of `provider:model` pairs that work reliably with Multi-Agent workflows.

---

## 7. GUI Elements

### 7.1 Main Window Sections

| Section | Widgets | Config Target |
|---------|---------|---------------|
| **Presets** | Preset dropdown, Load/Save buttons | `presets.yaml` |
| **General** | Iterations slider, One-file checkbox | `config.yaml` |
| **Paths** | Input/Output/Instructions/Guidelines line edits | `config.yaml` |
| **FPF Providers** | Provider/Model combos, Grounding slider | `fpf_config.yaml` |
| **GPTR/DR Providers** | Provider/Model combos, Token sliders | `default.py` |
| **Evaluation** | Iterations slider, Top-N slider, Mode radios, Judges checkboxes | `config.yaml` eval section |
| **Combine & Revise** | Enable checkbox, Model checkboxes | `config.yaml` combine section |

### 7.2 FPF Section Widgets

| Widget | Type | Maps To |
|--------|------|---------|
| `comboFPFProvider` | QComboBox | Provider selection |
| `comboFPFModel` | QComboBox | Model selection |
| `sliderGroundingMaxResults` | QSlider | `fpf.grounding.max_results` |
| `sliderGoogleMaxTokens` | QSlider | `fpf.google.max_tokens` |
| `comboFPFReasoningEffort` | QComboBox | `fpf.reasoning.effort` |
| `comboFPFWebSearchContextSize` | QComboBox | `fpf.web_search.search_context_size` |
| `groupProvidersFPF` | QGroupBox (checkable) | Enable/disable FPF |

### 7.3 GPTR Section Widgets

| Widget | Type | Maps To |
|--------|------|---------|
| `comboGPTRProvider` | QComboBox | Provider selection |
| `comboGPTRModel` | QComboBox | Model selection |
| `sliderFastTokenLimit` | QSlider | `FAST_TOKEN_LIMIT` |
| `sliderSmartTokenLimit` | QSlider | `SMART_TOKEN_LIMIT` |
| `sliderStrategicTokenLimit` | QSlider | `STRATEGIC_TOKEN_LIMIT` |
| `sliderBrowseChunkMaxLength` | QSlider | `BROWSE_CHUNK_MAX_LENGTH` |
| `sliderSummaryTokenLimit` | QSlider | `SUMMARY_TOKEN_LIMIT` |
| `sliderTemperature` | QSlider | `TEMPERATURE` (0-100 → 0.0-1.0) |
| `sliderMaxSearchResultsPerQuery` | QSlider | `MAX_SEARCH_RESULTS_PER_QUERY` |
| `sliderTotalWords` | QSlider | `TOTAL_WORDS` |
| `sliderMaxIterations` | QSlider | `MAX_ITERATIONS` |
| `sliderMaxSubtopics` | QSlider | `MAX_SUBTOPICS` |
| `sliderDeepResearchBreadth` | QSlider | `DEEP_RESEARCH_BREADTH` |
| `sliderDeepResearchDepth` | QSlider | `DEEP_RESEARCH_DEPTH` |
| `groupProvidersGPTR` | QGroupBox (checkable) | Enable/disable GPTR |
| `groupProvidersDR` | QGroupBox (checkable) | Enable/disable DR |

### 7.4 Evaluation Section Widgets

| Widget | Type | Maps To |
|--------|------|---------|
| `sliderEvaluationIterations` | QSlider | `eval.iterations` |
| `sliderPairwiseTopN` | QSlider | `eval.pairwise_top_n` |
| `radioEvalBoth` | QRadioButton | `eval.mode = both` |
| `radioEvalPairwise` | QRadioButton | `eval.mode = pairwise` |
| `radioEvalGraded` | QRadioButton | `eval.mode = single` |
| `containerEvalModels` | QWidget | Judge model checkboxes |
| `comboEvalModelA` | QComboBox | Unified eval Model A |
| `comboEvalModelB` | QComboBox | Unified eval Model B |
| `lineEvalOutputFolder` | QLineEdit | `eval.output_directory` |
| `lineEvalExportFolder` | QLineEdit | `eval.export_directory` |
| `checkEvalAutoRun` | QCheckBox | `eval.auto_run` |
| `groupEvaluation` | QGroupBox (checkable) | Enable single-doc eval |
| `groupEvaluation2` | QGroupBox (checkable) | Enable pairwise eval |

### 7.5 Combine Section Widgets

| Widget | Type | Maps To |
|--------|------|---------|
| `chkEnableCombine` | QCheckBox | `combine.enabled` |
| `containerCombineModels` | QWidget | Model checkboxes for combine |

### 7.6 Action Buttons

| Button | Object Name | Action |
|--------|-------------|--------|
| Write to Configs | `pushButton_3` | Save all UI values to config files |
| Execute | `btnAction7` | Execute generate.py with current config |
| Evaluate | `btnEvaluate` | Execute evaluate.py |
| Load Preset | `btnAction4` | Load selected preset |
| Save Preset | `btnAction5` | Save current values as preset |
| Execute One File | `btnAction6` | Execute with `one_file_only=true` |
| Download and Install | `pushButton_2` | Download dependencies |
| Open PM Config | `btnOpenPMConfig` | Open config.yaml in editor |
| Open .env | `btnAction8` | Open .env file |
| Open GPT-R Config | `btnAction1` | Open default.py |
| Open FPF Config | `btnAction2` | Open fpf_config.yaml |

---

## 8. ACM 2.0 Requirements Summary

Based on this analysis, ACM 2.0 must support:

### 8.1 Run Configuration
- [ ] Input/output/instructions/guidelines paths (or GitHub refs)
- [ ] Iterations per document
- [ ] Run definitions: type (fpf/gptr), provider, model
- [ ] One-file-only mode

### 8.2 Generator Parameters
- [ ] FPF: grounding results, max tokens, reasoning effort, web search context
- [ ] GPTR: all token limits, temperature, search limits, word counts, iterations, subtopics, research depth/breadth

### 8.3 Concurrency
- [ ] Max concurrent executions per generator type
- [ ] Launch delay between executions
- [ ] Enforce/cap policies

### 8.4 Evaluation
- [ ] Evaluation iterations
- [ ] Pairwise top-N selection
- [ ] Evaluation mode (single/pairwise/both)
- [ ] Multiple judge models
- [ ] Auto-execute after generation
- [ ] Output/export directories

### 8.5 Combine Phase
- [ ] Enable/disable combine
- [ ] Models for combine/revise

### 8.6 Presets
- [ ] Named preset storage
- [ ] Load/save presets
- [ ] Complete configuration bundles

### 8.7 Model Registry
- [ ] Provider definitions with models
- [ ] Context windows, API params, quirks
- [ ] Generator-specific model allowlists

### 8.8 Logging
- [ ] Console/file log levels
- [ ] Subprocess output forwarding
