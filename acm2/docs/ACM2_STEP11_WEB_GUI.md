# ACM 2.0 – Step 11: Web GUI

**Status:** Draft  
**Author:** Development Team  
**Last Updated:** 2025-12-04

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Dependency:** This step requires Steps 7 (Run/Doc API), 9 (FPF Adapter), and 10 (Evaluation) to be complete.  
> **Document Type:** Implementation specification for the code writer. Code samples are illustrative, not copy-paste ready.

---

## 1. Purpose

Step 11 delivers the **web-based configuration GUI** for ACM 2.0—a modern, responsive single-page application (SPA) that provides the same functionality as the ACM 1.0 desktop GUI but runs in a web browser.

**This step delivers:**
- A beautiful, responsive web UI for configuring and monitoring ACM runs
- Run creation wizard with document selection, generator config, eval settings
- Run list with filtering, status badges, and real-time updates
- Run detail view with progress tracking, document status, and report links
- Settings management for API keys, default repos, and preferences

**This step does NOT include:**
- User authentication (single-user mode uses no auth)
- Multi-tenant features (added in SaaS conversion)
- Mobile-specific layouts (responsive but desktop-first)

## 2. Architecture Decision

### 2.1 Static SPA Served by FastAPI (Hybrid Approach)

ACM 2.0 uses a **hybrid architecture**:

| Mode | Frontend | Backend | User Access |
|------|----------|---------|-------------|
| **Development** | Vite dev server (hot reload) | FastAPI (separate process) | `localhost:5173` |
| **Production** | Built static files | FastAPI serves everything | `localhost:8000` |
| **SaaS** | CDN (CloudFront/Vercel) | FastAPI on AWS | `app.acm.example.com` |

**Why this approach:**
- Single `acm2 serve` command starts everything
- No CORS issues in production (same origin)
- Frontend can be deployed to CDN independently for SaaS
- Hot reload during development for fast iteration

### 2.2 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Framework** | Svelte 5 | Lightweight, fast, excellent DX, compiles to vanilla JS |
| **Styling** | Tailwind CSS 4 | Utility-first, consistent design, small bundle |
| **Components** | Skeleton UI | Svelte-native component library, accessible |
| **Icons** | Lucide Svelte | Clean, consistent icon set |
| **HTTP Client** | Fetch API + SWR pattern | Native, simple, with caching/revalidation |
| **State** | Svelte stores | Built-in reactivity, no external library needed |
| **Build** | Vite | Fast builds, great dev experience |
| **Types** | TypeScript | Type safety, better IDE support |

**Alternative stacks (if you prefer):**
- React + shadcn/ui + Tailwind
- Vue 3 + PrimeVue + Tailwind
- SolidJS + Kobalte + Tailwind

## 3. Project Structure

```
acm2/
├── app/                           # FastAPI backend (existing)
│   ├── main.py                    # Serves UI in production
│   └── ...
├── ui/                            # Frontend source
│   ├── src/
│   │   ├── app.html               # HTML shell
│   │   ├── app.css                # Global styles (Tailwind imports)
│   │   ├── routes/
│   │   │   ├── +layout.svelte     # App shell with nav
│   │   │   ├── +page.svelte       # Dashboard / run list
│   │   │   ├── configure/
│   │   │   │   └── +page.svelte   # ACM 1.0-style config page (main)
│   │   │   ├── runs/
│   │   │   │   ├── +page.svelte   # Run list
│   │   │   │   ├── new/
│   │   │   │   │   └── +page.svelte   # Create run wizard
│   │   │   │   └── [run_id]/
│   │   │   │       ├── +page.svelte   # Run detail
│   │   │   │       └── combine/
│   │   │   │           └── +page.svelte   # Combine artifacts
│   │   │   ├── documents/
│   │   │   │   └── +page.svelte   # Document browser
│   │   │   └── settings/
│   │   │       └── +page.svelte   # Settings page
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   │   ├── client.ts      # API client with fetch wrapper
│   │   │   │   ├── runs.ts        # Run API functions
│   │   │   │   ├── documents.ts   # Document API functions
│   │   │   │   └── execution.ts   # Generate/Evaluate API functions
│   │   │   ├── components/
│   │   │   │   ├── RunCard.svelte
│   │   │   │   ├── RunStatusBadge.svelte
│   │   │   │   ├── DocumentPicker.svelte
│   │   │   │   └── config/                    # ACM 1.0-style config components
│   │   │   │       ├── ProvidersPanel.svelte      # Model selection checkboxes
│   │   │   │       ├── PathsEvalPanel.svelte      # Paths + evaluation settings
│   │   │   │       ├── GptrParamsPanel.svelte     # All sliders (20+)
│   │   │   │       ├── CombinePanel.svelte        # Combine settings
│   │   │   │       ├── RuntimeMetrics.svelte      # Progress metrics bar
│   │   │   │       ├── ActionButtons.svelte       # Bottom action buttons
│   │   │   │       ├── PresetSelector.svelte      # Preset dropdown
│   │   │   │       └── ModelCheckboxList.svelte   # Reusable checkbox list
│   │   │   ├── stores/
│   │   │   │   ├── config.ts      # RunConfig store (all settings)
│   │   │   │   ├── presets.ts     # Presets store
│   │   │   │   ├── modelCatalog.ts # Available models per generator
│   │   │   │   ├── run.ts         # Current run state/progress
│   │   │   │   └── settings.ts    # User settings store
│   │   │   └── types/
│   │   │       ├── run.ts         # Run type definitions
│   │   │       ├── config.ts      # Config type definitions
│   │   │       └── document.ts    # Document type definitions
│   │   └── static/
│   │       └── favicon.png
│   ├── package.json
│   ├── svelte.config.js
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
└── pyproject.toml                 # Backend deps
```

## 4. FastAPI Static File Serving

### 4.1 Production Mode (Serve Built UI)

```python
# app/main.py
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

def create_app() -> FastAPI:
    app = FastAPI(title="ACM 2.0", version="2.0.0")
    
    # Mount API routes first (they take priority)
    app.include_router(api_router, prefix="/api/v1")
    
    # Serve static UI files in production
    ui_dist = Path(__file__).parent.parent / "ui" / "dist"
    if ui_dist.exists():
        # Serve static assets (JS, CSS, images)
        app.mount("/assets", StaticFiles(directory=ui_dist / "assets"), name="assets")
        
        # Serve index.html for all other routes (SPA fallback)
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # Check if it's a file that exists
            file_path = ui_dist / path
            if file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html (SPA routing)
            return FileResponse(ui_dist / "index.html")
    
    return app
```

### 4.2 Development Mode (CORS for Separate Frontend)

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(...)
    
    settings = get_settings()
    if settings.dev_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:5173",    # Vite dev server
                "http://localhost:3000",    # Alternative dev server
                "http://127.0.0.1:5173",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # ... rest of setup
```

### 4.3 Vite Proxy Configuration (Dev Mode)

```typescript
// ui/vite.config.ts
import { defineConfig } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to FastAPI backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

## 5. UI Components

### 5.0 ACM 1.0 Parity Requirements

The ACM 2.0 Web GUI must provide **at least** all the same controls as ACM 1.0's desktop GUI. This section specifies the complete control inventory.

#### 5.0.1 Complete Slider Inventory (17 sliders)

| Section | Slider | Range | Maps To |
|---------|--------|-------|---------|
| **General** | Master Quality | 1-9 | Preset selector (maps to low/medium/high/888) |
| **General** | Iterations | 1-9 | `iterations_default` |
| **FPF** | Grounding Max Results | 1-10 | `fpf.grounding.max_results` |
| **FPF** | Max Output Tokens | 1000-200000 | `fpf.google.max_tokens` |
| **GPTR** | Fast Token Limit | 3000-87538 | `FAST_TOKEN_LIMIT` |
| **GPTR** | Smart Token Limit | 6000-175038 | `SMART_TOKEN_LIMIT` |
| **GPTR** | Strategic Token Limit | 4000-87538 | `STRATEGIC_TOKEN_LIMIT` |
| **GPTR** | Browse Chunk Max Length | 8192-26262 | `BROWSE_CHUNK_MAX_LENGTH` |
| **GPTR** | Summary Token Limit | 700-1759 | `SUMMARY_TOKEN_LIMIT` |
| **GPTR** | Temperature | 0-100 (→0.0-1.0) | `TEMPERATURE` |
| **GPTR** | Max Search Results | 1-8 | `MAX_SEARCH_RESULTS_PER_QUERY` |
| **GPTR** | Total Words | 1200-43762 | `TOTAL_WORDS` |
| **GPTR** | Max Iterations | 1-8 | `MAX_ITERATIONS` |
| **GPTR** | Max Subtopics | 1-9 | `MAX_SUBTOPICS` |
| **DR** | Deep Research Breadth | 1-8 | `DEEP_RESEARCH_BREADTH` |
| **DR** | Deep Research Depth | 1-8 | `DEEP_RESEARCH_DEPTH` |
| **Eval** | Evaluation Iterations | 1-9 | `eval.iterations` |
| **Eval** | Pairwise Top-N | 1-10 | `eval.pairwise_top_n` |
| **Concurrency** | Max Concurrent Reports | 1-20 | `concurrency.max_concurrent_reports` |
| **Concurrency** | Launch Delay (seconds) | 0.1-5.0 | `concurrency.launch_delay_seconds` |

#### 5.0.2 Complete Checkbox Inventory

| Section | Checkbox | Maps To |
|---------|----------|---------|
| **Generators** | Enable FPF (group checkbox) | `enable.fpf` |
| **Generators** | Enable GPTR (group checkbox) | `enable.gptr` |
| **Generators** | Enable DR (group checkbox) | `enable.dr` |
| **Generators** | Enable MA (group checkbox) | `enable.ma` |
| **FPF Models** | Checkbox per `provider:model` | `runs[]` with type=fpf |
| **GPTR Models** | Checkbox per `provider:model` | `runs[]` with type=gptr |
| **DR Models** | Checkbox per `provider:model` | `runs[]` with type=dr |
| **MA Models** | Checkbox per `provider:model` | `runs[]` with type=ma |
| **Paths** | Follow Guidelines | `follow_guidelines` |
| **Eval** | Auto-run Evaluation | `eval.auto_run` |
| **Eval** | Enable Single-Doc Eval | `eval.mode` includes single |
| **Eval** | Enable Pairwise Eval | `eval.mode` includes pairwise |
| **Eval** | Judge model checkboxes | `eval.judges[]` |
| **Combine** | Enable Combine Step | `combine.enabled` |
| **Combine** | Combine model checkboxes | `combine.models[]` |

#### 5.0.3 Complete Dropdown Inventory

| Section | Dropdown | Options |
|---------|----------|---------|
| **Presets** | Preset Selector | Load from `presets.yaml` |
| **FPF** | Reasoning Effort | low, medium, high |
| **FPF** | Web Search Context Size | low, medium, high |
| **Eval** | Evaluation Mode | single, pairwise, both |
| **Logging** | Console Log Level | low, medium, high |
| **Logging** | File Log Level | low, medium, high |

#### 5.0.4 GUI Section Layout (matching ACM 1.0)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Header: ACM 2.0                                              [Presets ▼] [⚙] │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┬─────────────────┬─────────────────┬────────────────────┐ │
│ │ PROVIDERS       │ PATHS &         │ GPTR/DR/MA      │ COMBINE &          │ │
│ │ (Model Select)  │ EVALUATION      │ PARAMETERS      │ REVISE             │ │
│ │                 │                 │                 │                    │ │
│ │ ☑ FPF           │ input_folder    │ Fast Token:     │ ☐ Enable Combine   │ │
│ │   ☐ openai:4.1  │ [Browse] [Open] │ ═══════●══ 8000 │                    │ │
│ │   ☐ google:2.5  │                 │                 │ Select models:     │ │
│ │   ☐ anthro:3.5  │ output_folder   │ Smart Token:    │ ☐ openai:gpt-5.1   │ │
│ │                 │ [Browse] [Open] │ ═══════●══ 16k  │ ☐ google:gemini    │ │
│ │ ☑ GPTR          │                 │                 │                    │ │
│ │   ☐ openai:4.1  │ instructions    │ Strategic:      │                    │ │
│ │   ☐ google:2.5  │ [Browse] [Open] │ ═══════●══ 8000 │                    │ │
│ │                 │                 │                 │                    │ │
│ │ ☑ DR            │ guidelines      │ Temperature:    │                    │ │
│ │   ☐ openai:4.1  │ [Browse] [Open] │ ═══════●══ 0.4  │                    │ │
│ │   ☐ google:2.5  │ ☐ Follow Guidel │                 │                    │ │
│ │                 │                 │ Search Results: │                    │ │
│ │ ☑ MA            │ ──────────────  │ ═══════●══ 4    │                    │ │
│ │   ☐ openai:4.1  │ EVALUATION      │                 │                    │ │
│ │   ☐ openai:o4   │                 │ Total Words:    │                    │ │
│ │                 │ ☑ Enable Eval   │ ═══════●══ 8000 │                    │ │
│ │                 │ ☐ Auto-run      │                 │                    │ │
│ │                 │                 │ Max Iterations: │                    │ │
│ │                 │ Mode: [both ▼]  │ ═══════●══ 3    │                    │ │
│ │                 │                 │                 │                    │ │
│ │                 │ Iterations:     │ Max Subtopics:  │                    │ │
│ │                 │ ═══════●══ 1    │ ═══════●══ 3    │                    │ │
│ │                 │                 │                 │                    │ │
│ │                 │ Pairwise Top-N: │ DR Breadth:     │                    │ │
│ │                 │ ═══════●══ 3    │ ═══════●══ 3    │                    │ │
│ │                 │                 │                 │                    │ │
│ │                 │ Judges:         │ DR Depth:       │                    │ │
│ │                 │ ☐ openai:gpt-5  │ ═══════●══ 2    │                    │ │
│ │                 │ ☐ google:gemini │                 │                    │ │
│ └─────────────────┴─────────────────┴─────────────────┴────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ Runtime Metrics: Files: 12 | Reports: 0/48 | Evals: 0/96 | Progress ═══●═══ │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Load Preset] [Save Preset] [Write Config] [Run One] [Generate] [Evaluate]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 App Shell (Layout)

```svelte
<!-- ui/src/routes/+layout.svelte -->
<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import { AppShell, AppBar, AppRail, AppRailTile } from '@skeletonlabs/skeleton';
  import { Home, Play, FileText, Settings, Github, Sliders } from 'lucide-svelte';
</script>

<AppShell>
  <!-- Header -->
  <svelte:fragment slot="header">
    <AppBar>
      <svelte:fragment slot="lead">
        <strong class="text-xl">ACM 2.0</strong>
      </svelte:fragment>
      <svelte:fragment slot="trail">
        <a href="https://github.com/yourorg/acm2" target="_blank" class="btn btn-sm variant-ghost">
          <Github size={18} />
        </a>
      </svelte:fragment>
    </AppBar>
  </svelte:fragment>
  
  <!-- Sidebar Navigation -->
  <svelte:fragment slot="sidebarLeft">
    <AppRail>
      <AppRailTile href="/" selected={$page.url.pathname === '/'}>
        <svelte:fragment slot="lead"><Home size={20} /></svelte:fragment>
        <span>Dashboard</span>
      </AppRailTile>
      <AppRailTile href="/configure" selected={$page.url.pathname.startsWith('/configure')}>
        <svelte:fragment slot="lead"><Sliders size={20} /></svelte:fragment>
        <span>Configure</span>
      </AppRailTile>
      <AppRailTile href="/runs" selected={$page.url.pathname.startsWith('/runs')}>
        <svelte:fragment slot="lead"><Play size={20} /></svelte:fragment>
        <span>Runs</span>
      </AppRailTile>
      <AppRailTile href="/documents" selected={$page.url.pathname.startsWith('/documents')}>
        <svelte:fragment slot="lead"><FileText size={20} /></svelte:fragment>
        <span>Documents</span>
      </AppRailTile>
      <AppRailTile href="/settings" selected={$page.url.pathname.startsWith('/settings')}>
        <svelte:fragment slot="lead"><Settings size={20} /></svelte:fragment>
        <span>Settings</span>
      </AppRailTile>
    </AppRail>
  </svelte:fragment>
  
  <!-- Main Content -->
  <div class="container mx-auto p-4">
    <slot />
  </div>
</AppShell>
```

### 5.2 Configuration Page (ACM 1.0 Parity)

This is the main configuration page that replicates all ACM 1.0 desktop GUI functionality.

```svelte
<!-- ui/src/routes/configure/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import ProvidersPanel from '$lib/components/config/ProvidersPanel.svelte';
  import PathsEvalPanel from '$lib/components/config/PathsEvalPanel.svelte';
  import GptrParamsPanel from '$lib/components/config/GptrParamsPanel.svelte';
  import CombinePanel from '$lib/components/config/CombinePanel.svelte';
  import RuntimeMetrics from '$lib/components/config/RuntimeMetrics.svelte';
  import ActionButtons from '$lib/components/config/ActionButtons.svelte';
  import PresetSelector from '$lib/components/config/PresetSelector.svelte';
  import { configStore, loadConfig, saveConfig } from '$lib/stores/config';
  import { presetsStore, loadPresets } from '$lib/stores/presets';
  import { modelCatalog, loadModelCatalog } from '$lib/stores/modelCatalog';
  
  let loading = true;
  
  onMount(async () => {
    await Promise.all([
      loadConfig(),
      loadPresets(),
      loadModelCatalog(),
    ]);
    loading = false;
  });
</script>

<div class="space-y-4">
  <!-- Header with Preset Selector -->
  <div class="flex justify-between items-center">
    <h1 class="h2">Run Configuration</h1>
    <PresetSelector />
  </div>
  
  {#if loading}
    <div class="flex justify-center p-8">
      <div class="animate-spin text-4xl">⏳</div>
    </div>
  {:else}
    <!-- Main 4-Column Layout (matches ACM 1.0) -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <!-- Column 1: Providers (Model Selection) -->
      <div class="lg:col-span-1">
        <ProvidersPanel />
      </div>
      
      <!-- Column 2: Paths & Evaluation -->
      <div class="lg:col-span-1">
        <PathsEvalPanel />
      </div>
      
      <!-- Column 3: GPTR/DR/MA Parameters -->
      <div class="lg:col-span-1">
        <GptrParamsPanel />
      </div>
      
      <!-- Column 4: Combine & Revise -->
      <div class="lg:col-span-1">
        <CombinePanel />
      </div>
    </div>
    
    <!-- Runtime Metrics Bar -->
    <RuntimeMetrics />
    
    <!-- Action Buttons -->
    <ActionButtons />
  {/if}
</div>
```

### 5.2.1 Providers Panel (Model Selection with Checkboxes)

```svelte
<!-- ui/src/lib/components/config/ProvidersPanel.svelte -->
<script lang="ts">
  import { SlideToggle } from '@skeletonlabs/skeleton';
  import { configStore } from '$lib/stores/config';
  import { modelCatalog } from '$lib/stores/modelCatalog';
  import ModelCheckboxList from './ModelCheckboxList.svelte';
  
  // Generator enable toggles
  $: fpfEnabled = $configStore.enable?.fpf ?? true;
  $: gptrEnabled = $configStore.enable?.gptr ?? true;
  $: drEnabled = $configStore.enable?.dr ?? true;
  $: maEnabled = $configStore.enable?.ma ?? true;
  
  // Selected models per generator type
  $: selectedFpf = $configStore.runs?.filter(r => r.type === 'fpf').map(r => `${r.provider}:${r.model}`) ?? [];
  $: selectedGptr = $configStore.runs?.filter(r => r.type === 'gptr').map(r => `${r.provider}:${r.model}`) ?? [];
  $: selectedDr = $configStore.runs?.filter(r => r.type === 'dr').map(r => `${r.provider}:${r.model}`) ?? [];
  $: selectedMa = $configStore.runs?.filter(r => r.type === 'ma').map(r => `${r.provider}:${r.model}`) ?? [];
  
  function updateRuns(type: string, selected: string[]) {
    configStore.update(cfg => {
      const otherRuns = cfg.runs?.filter(r => r.type !== type) ?? [];
      const newRuns = selected.map(pm => {
        const [provider, model] = pm.split(':');
        return { type, provider, model };
      });
      return { ...cfg, runs: [...otherRuns, ...newRuns] };
    });
  }
  
  function toggleGenerator(type: string, enabled: boolean) {
    configStore.update(cfg => ({
      ...cfg,
      enable: { ...cfg.enable, [type]: enabled }
    }));
  }
</script>

<div class="card p-4 space-y-4 h-full overflow-y-auto">
  <h3 class="h4">Report Types: Model Selection</h3>
  
  <!-- FPF Section -->
  <div class="card variant-soft p-3">
    <div class="flex items-center justify-between mb-2">
      <span class="font-semibold">FPF (FilePromptForge)</span>
      <SlideToggle 
        name="fpf-toggle" 
        size="sm" 
        checked={fpfEnabled}
        on:change={(e) => toggleGenerator('fpf', e.target.checked)}
      />
    </div>
    {#if fpfEnabled}
      <p class="text-xs text-surface-500 mb-2">Select models (provider:model):</p>
      <ModelCheckboxList 
        models={$modelCatalog.fpf} 
        selected={selectedFpf}
        on:change={(e) => updateRuns('fpf', e.detail)}
      />
    {/if}
  </div>
  
  <!-- GPTR Section -->
  <div class="card variant-soft p-3">
    <div class="flex items-center justify-between mb-2">
      <span class="font-semibold">GPTR (GPT Researcher)</span>
      <SlideToggle 
        name="gptr-toggle" 
        size="sm" 
        checked={gptrEnabled}
        on:change={(e) => toggleGenerator('gptr', e.target.checked)}
      />
    </div>
    {#if gptrEnabled}
      <p class="text-xs text-surface-500 mb-2">Select models (provider:model):</p>
      <ModelCheckboxList 
        models={$modelCatalog.gptr} 
        selected={selectedGptr}
        on:change={(e) => updateRuns('gptr', e.detail)}
      />
    {/if}
  </div>
  
  <!-- DR Section -->
  <div class="card variant-soft p-3">
    <div class="flex items-center justify-between mb-2">
      <span class="font-semibold">DR (Deep Research)</span>
      <SlideToggle 
        name="dr-toggle" 
        size="sm" 
        checked={drEnabled}
        on:change={(e) => toggleGenerator('dr', e.target.checked)}
      />
    </div>
    {#if drEnabled}
      <p class="text-xs text-surface-500 mb-2">Select models (provider:model):</p>
      <ModelCheckboxList 
        models={$modelCatalog.dr} 
        selected={selectedDr}
        on:change={(e) => updateRuns('dr', e.detail)}
      />
    {/if}
  </div>
  
  <!-- MA Section -->
  <div class="card variant-soft p-3">
    <div class="flex items-center justify-between mb-2">
      <span class="font-semibold">MA (Multi-Agent Task)</span>
      <SlideToggle 
        name="ma-toggle" 
        size="sm" 
        checked={maEnabled}
        on:change={(e) => toggleGenerator('ma', e.target.checked)}
      />
    </div>
    {#if maEnabled}
      <p class="text-xs text-surface-500 mb-2">Select models (provider:model):</p>
      <ModelCheckboxList 
        models={$modelCatalog.ma} 
        selected={selectedMa}
        on:change={(e) => updateRuns('ma', e.detail)}
      />
    {/if}
  </div>
</div>
```

### 5.2.2 Model Checkbox List Component

```svelte
<!-- ui/src/lib/components/config/ModelCheckboxList.svelte -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let models: string[] = [];
  export let selected: string[] = [];
  
  const dispatch = createEventDispatcher<{ change: string[] }>();
  
  function toggle(model: string) {
    if (selected.includes(model)) {
      selected = selected.filter(m => m !== model);
    } else {
      selected = [...selected, model];
    }
    dispatch('change', selected);
  }
</script>

<div class="space-y-1 max-h-40 overflow-y-auto">
  {#each models as model}
    <label class="flex items-center gap-2 cursor-pointer hover:bg-surface-500/10 p-1 rounded">
      <input 
        type="checkbox" 
        class="checkbox checkbox-sm"
        checked={selected.includes(model)}
        on:change={() => toggle(model)}
      />
      <span class="text-sm">{model}</span>
    </label>
  {/each}
  {#if models.length === 0}
    <p class="text-xs text-surface-400 italic">No models available</p>
  {/if}
</div>
```

### 5.2.3 Paths & Evaluation Panel

```svelte
<!-- ui/src/lib/components/config/PathsEvalPanel.svelte -->
<script lang="ts">
  import { RangeSlider, SlideToggle } from '@skeletonlabs/skeleton';
  import { FolderOpen, FileText } from 'lucide-svelte';
  import { configStore } from '$lib/stores/config';
  import { modelCatalog } from '$lib/stores/modelCatalog';
  import ModelCheckboxList from './ModelCheckboxList.svelte';
  
  // Path values
  $: inputFolder = $configStore.input_folder ?? '';
  $: outputFolder = $configStore.output_folder ?? '';
  $: instructionsFile = $configStore.instructions_file ?? '';
  $: guidelinesFile = $configStore.guidelines_file ?? '';
  $: followGuidelines = $configStore.follow_guidelines ?? false;
  
  // Eval values
  $: evalEnabled = $configStore.eval?.enabled ?? true;
  $: evalAutoRun = $configStore.eval?.auto_run ?? true;
  $: evalMode = $configStore.eval?.mode ?? 'both';
  $: evalIterations = $configStore.eval?.iterations ?? 1;
  $: pairwiseTopN = $configStore.eval?.pairwise_top_n ?? 3;
  $: evalOutputDir = $configStore.eval?.output_directory ?? '';
  $: evalExportDir = $configStore.eval?.export_directory ?? '';
  $: selectedJudges = $configStore.eval?.judges?.map(j => `${j.provider}:${j.model}`) ?? [];
  
  function updatePath(field: string, value: string) {
    configStore.update(cfg => ({ ...cfg, [field]: value }));
  }
  
  function updateEval(field: string, value: any) {
    configStore.update(cfg => ({
      ...cfg,
      eval: { ...cfg.eval, [field]: value }
    }));
  }
  
  function updateJudges(selected: string[]) {
    const judges = selected.map(pm => {
      const [provider, model] = pm.split(':');
      return { provider, model };
    });
    updateEval('judges', judges);
  }
  
  async function browseFolder(field: string) {
    // In web, we'll use the File System Access API or a file picker modal
    // For now, show a prompt (in production, use proper file picker)
    const path = prompt(`Enter path for ${field}:`, $configStore[field] || '');
    if (path) updatePath(field, path);
  }
</script>

<div class="card p-4 space-y-4 h-full overflow-y-auto">
  <!-- Paths Section -->
  <div class="space-y-3">
    <h3 class="h4">Paths</h3>
    
    <!-- Input Folder -->
    <div class="space-y-1">
      <label class="text-sm font-medium">input_folder</label>
      <div class="input-group">
        <input 
          type="text" 
          class="input text-xs" 
          value={inputFolder}
          on:input={(e) => updatePath('input_folder', e.target.value)}
        />
        <button class="variant-soft-surface" on:click={() => browseFolder('input_folder')}>
          <FolderOpen size={16} />
        </button>
      </div>
    </div>
    
    <!-- Output Folder -->
    <div class="space-y-1">
      <label class="text-sm font-medium">output_folder</label>
      <div class="input-group">
        <input 
          type="text" 
          class="input text-xs" 
          value={outputFolder}
          on:input={(e) => updatePath('output_folder', e.target.value)}
        />
        <button class="variant-soft-surface" on:click={() => browseFolder('output_folder')}>
          <FolderOpen size={16} />
        </button>
      </div>
    </div>
    
    <!-- Instructions File -->
    <div class="space-y-1">
      <label class="text-sm font-medium">instructions_file</label>
      <div class="input-group">
        <input 
          type="text" 
          class="input text-xs" 
          value={instructionsFile}
          on:input={(e) => updatePath('instructions_file', e.target.value)}
        />
        <button class="variant-soft-surface" on:click={() => browseFolder('instructions_file')}>
          <FileText size={16} />
        </button>
      </div>
    </div>
    
    <!-- Guidelines File -->
    <div class="space-y-1">
      <label class="text-sm font-medium">guidelines_file</label>
      <div class="input-group">
        <input 
          type="text" 
          class="input text-xs" 
          value={guidelinesFile}
          on:input={(e) => updatePath('guidelines_file', e.target.value)}
        />
        <button class="variant-soft-surface" on:click={() => browseFolder('guidelines_file')}>
          <FileText size={16} />
        </button>
      </div>
    </div>
    
    <label class="flex items-center gap-2">
      <input 
        type="checkbox" 
        class="checkbox"
        checked={followGuidelines}
        on:change={(e) => updatePath('follow_guidelines', e.target.checked)}
      />
      <span class="text-sm">Follow Guidelines</span>
    </label>
  </div>
  
  <hr class="!border-t-2" />
  
  <!-- Evaluation Section -->
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <h3 class="h4">Evaluation</h3>
      <SlideToggle 
        name="eval-toggle" 
        size="sm"
        checked={evalEnabled}
        on:change={(e) => updateEval('enabled', e.target.checked)}
      />
    </div>
    
    {#if evalEnabled}
      <label class="flex items-center gap-2">
        <input 
          type="checkbox" 
          class="checkbox"
          checked={evalAutoRun}
          on:change={(e) => updateEval('auto_run', e.target.checked)}
        />
        <span class="text-sm">Auto-run after Generation</span>
      </label>
      
      <!-- Eval Mode -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Mode</label>
        <select 
          class="select text-sm"
          value={evalMode}
          on:change={(e) => updateEval('mode', e.target.value)}
        >
          <option value="single">Single-doc only</option>
          <option value="pairwise">Pairwise only</option>
          <option value="both">Both</option>
        </select>
      </div>
      
      <!-- Eval Iterations Slider -->
      <div class="space-y-1">
        <div class="flex justify-between text-sm">
          <span>Iterations</span>
          <span class="font-mono">{evalIterations}</span>
        </div>
        <RangeSlider 
          name="eval-iterations" 
          min={1} 
          max={9} 
          step={1}
          bind:value={evalIterations}
          on:change={(e) => updateEval('iterations', e.target.value)}
        />
      </div>
      
      <!-- Pairwise Top-N Slider -->
      <div class="space-y-1">
        <div class="flex justify-between text-sm">
          <span>Pairwise Top-N</span>
          <span class="font-mono">{pairwiseTopN}</span>
        </div>
        <RangeSlider 
          name="pairwise-topn" 
          min={1} 
          max={10} 
          step={1}
          bind:value={pairwiseTopN}
          on:change={(e) => updateEval('pairwise_top_n', e.target.value)}
        />
      </div>
      
      <!-- Eval Output Directory -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Eval Output Dir</label>
        <input 
          type="text" 
          class="input text-xs" 
          value={evalOutputDir}
          on:input={(e) => updateEval('output_directory', e.target.value)}
        />
      </div>
      
      <!-- Eval Export Directory -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Eval Export Dir</label>
        <input 
          type="text" 
          class="input text-xs" 
          value={evalExportDir}
          on:input={(e) => updateEval('export_directory', e.target.value)}
        />
      </div>
      
      <!-- Judge Models -->
      <div class="space-y-1">
        <label class="text-sm font-medium">Judge Models</label>
        <ModelCheckboxList 
          models={$modelCatalog.gptr} 
          selected={selectedJudges}
          on:change={(e) => updateJudges(e.detail)}
        />
      </div>
    {/if}
  </div>
</div>
```

### 5.2.4 GPTR/DR/MA Parameters Panel (All Sliders)

```svelte
<!-- ui/src/lib/components/config/GptrParamsPanel.svelte -->
<script lang="ts">
  import { RangeSlider } from '@skeletonlabs/skeleton';
  import { configStore } from '$lib/stores/config';
  
  // General settings
  $: iterationsDefault = $configStore.iterations_default ?? 1;
  
  // GPTR Token Limits
  $: fastTokenLimit = $configStore.gptr?.fast_token_limit ?? 8000;
  $: smartTokenLimit = $configStore.gptr?.smart_token_limit ?? 16000;
  $: strategicTokenLimit = $configStore.gptr?.strategic_token_limit ?? 8000;
  $: browseChunkMaxLength = $configStore.gptr?.browse_chunk_max_length ?? 8192;
  $: summaryTokenLimit = $configStore.gptr?.summary_token_limit ?? 700;
  
  // GPTR Research Parameters
  $: temperature = $configStore.gptr?.temperature ?? 0.4;
  $: maxSearchResults = $configStore.gptr?.max_search_results_per_query ?? 4;
  $: totalWords = $configStore.gptr?.total_words ?? 8000;
  $: maxIterations = $configStore.gptr?.max_iterations ?? 3;
  $: maxSubtopics = $configStore.gptr?.max_subtopics ?? 3;
  
  // DR Parameters
  $: deepResearchBreadth = $configStore.dr?.breadth ?? 3;
  $: deepResearchDepth = $configStore.dr?.depth ?? 2;
  
  // FPF Parameters
  $: fpfGroundingMaxResults = $configStore.fpf?.grounding_max_results ?? 3;
  $: fpfMaxTokens = $configStore.fpf?.max_tokens ?? 50000;
  $: fpfReasoningEffort = $configStore.fpf?.reasoning_effort ?? 'medium';
  $: fpfWebSearchContext = $configStore.fpf?.web_search_context_size ?? 'medium';
  
  // Concurrency
  $: maxConcurrentReports = $configStore.concurrency?.max_concurrent_reports ?? 11;
  $: launchDelaySeconds = $configStore.concurrency?.launch_delay_seconds ?? 0.5;
  
  // Temperature slider is 0-100, maps to 0.0-1.0
  $: temperatureSlider = Math.round(temperature * 100);
  
  function updateGptr(field: string, value: any) {
    configStore.update(cfg => ({
      ...cfg,
      gptr: { ...cfg.gptr, [field]: value }
    }));
  }
  
  function updateDr(field: string, value: any) {
    configStore.update(cfg => ({
      ...cfg,
      dr: { ...cfg.dr, [field]: value }
    }));
  }
  
  function updateFpf(field: string, value: any) {
    configStore.update(cfg => ({
      ...cfg,
      fpf: { ...cfg.fpf, [field]: value }
    }));
  }
  
  function updateConcurrency(field: string, value: any) {
    configStore.update(cfg => ({
      ...cfg,
      concurrency: { ...cfg.concurrency, [field]: value }
    }));
  }
  
  function updateRoot(field: string, value: any) {
    configStore.update(cfg => ({ ...cfg, [field]: value }));
  }
</script>

<div class="card p-4 space-y-4 h-full overflow-y-auto">
  <!-- General Section -->
  <div class="space-y-2">
    <h3 class="h4">General</h3>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Iterations</span>
        <span class="font-mono">{iterationsDefault}</span>
      </div>
      <RangeSlider 
        name="iterations" 
        min={1} 
        max={9} 
        step={1}
        bind:value={iterationsDefault}
        on:change={() => updateRoot('iterations_default', iterationsDefault)}
      />
    </div>
  </div>
  
  <hr class="!border-t-2" />
  
  <!-- FPF Parameters -->
  <div class="space-y-2">
    <h4 class="font-semibold text-sm">FPF Parameters</h4>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Grounding Results</span>
        <span class="font-mono">{fpfGroundingMaxResults}</span>
      </div>
      <RangeSlider 
        name="fpf-grounding" 
        min={1} 
        max={10} 
        step={1}
        bind:value={fpfGroundingMaxResults}
        on:change={() => updateFpf('grounding_max_results', fpfGroundingMaxResults)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Max Tokens</span>
        <span class="font-mono">{fpfMaxTokens.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="fpf-tokens" 
        min={1000} 
        max={200000} 
        step={1000}
        bind:value={fpfMaxTokens}
        on:change={() => updateFpf('max_tokens', fpfMaxTokens)}
      />
    </div>
    
    <div class="space-y-1">
      <label class="text-sm">Reasoning Effort</label>
      <select 
        class="select text-sm"
        bind:value={fpfReasoningEffort}
        on:change={() => updateFpf('reasoning_effort', fpfReasoningEffort)}
      >
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
    </div>
    
    <div class="space-y-1">
      <label class="text-sm">Web Search Context</label>
      <select 
        class="select text-sm"
        bind:value={fpfWebSearchContext}
        on:change={() => updateFpf('web_search_context_size', fpfWebSearchContext)}
      >
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
    </div>
  </div>
  
  <hr class="!border-t-2" />
  
  <!-- GPTR Token Limits -->
  <div class="space-y-2">
    <h4 class="font-semibold text-sm">GPTR Token Limits</h4>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Fast Token Limit</span>
        <span class="font-mono">{fastTokenLimit.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="fast-token" 
        min={3000} 
        max={87538} 
        step={500}
        bind:value={fastTokenLimit}
        on:change={() => updateGptr('fast_token_limit', fastTokenLimit)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Smart Token Limit</span>
        <span class="font-mono">{smartTokenLimit.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="smart-token" 
        min={6000} 
        max={175038} 
        step={500}
        bind:value={smartTokenLimit}
        on:change={() => updateGptr('smart_token_limit', smartTokenLimit)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Strategic Token Limit</span>
        <span class="font-mono">{strategicTokenLimit.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="strategic-token" 
        min={4000} 
        max={87538} 
        step={500}
        bind:value={strategicTokenLimit}
        on:change={() => updateGptr('strategic_token_limit', strategicTokenLimit)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Browse Chunk Length</span>
        <span class="font-mono">{browseChunkMaxLength.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="browse-chunk" 
        min={8192} 
        max={26262} 
        step={512}
        bind:value={browseChunkMaxLength}
        on:change={() => updateGptr('browse_chunk_max_length', browseChunkMaxLength)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Summary Token Limit</span>
        <span class="font-mono">{summaryTokenLimit.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="summary-token" 
        min={700} 
        max={1759} 
        step={50}
        bind:value={summaryTokenLimit}
        on:change={() => updateGptr('summary_token_limit', summaryTokenLimit)}
      />
    </div>
  </div>
  
  <hr class="!border-t-2" />
  
  <!-- GPTR Research Parameters -->
  <div class="space-y-2">
    <h4 class="font-semibold text-sm">GPTR Research</h4>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Temperature</span>
        <span class="font-mono">{temperature.toFixed(2)}</span>
      </div>
      <RangeSlider 
        name="temperature" 
        min={0} 
        max={100} 
        step={1}
        bind:value={temperatureSlider}
        on:change={() => updateGptr('temperature', temperatureSlider / 100)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Max Search Results</span>
        <span class="font-mono">{maxSearchResults}</span>
      </div>
      <RangeSlider 
        name="search-results" 
        min={1} 
        max={8} 
        step={1}
        bind:value={maxSearchResults}
        on:change={() => updateGptr('max_search_results_per_query', maxSearchResults)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Total Words</span>
        <span class="font-mono">{totalWords.toLocaleString()}</span>
      </div>
      <RangeSlider 
        name="total-words" 
        min={1200} 
        max={43762} 
        step={500}
        bind:value={totalWords}
        on:change={() => updateGptr('total_words', totalWords)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Max Iterations</span>
        <span class="font-mono">{maxIterations}</span>
      </div>
      <RangeSlider 
        name="max-iterations" 
        min={1} 
        max={8} 
        step={1}
        bind:value={maxIterations}
        on:change={() => updateGptr('max_iterations', maxIterations)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Max Subtopics</span>
        <span class="font-mono">{maxSubtopics}</span>
      </div>
      <RangeSlider 
        name="max-subtopics" 
        min={1} 
        max={9} 
        step={1}
        bind:value={maxSubtopics}
        on:change={() => updateGptr('max_subtopics', maxSubtopics)}
      />
    </div>
  </div>
  
  <hr class="!border-t-2" />
  
  <!-- DR Parameters -->
  <div class="space-y-2">
    <h4 class="font-semibold text-sm">Deep Research</h4>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Breadth</span>
        <span class="font-mono">{deepResearchBreadth}</span>
      </div>
      <RangeSlider 
        name="dr-breadth" 
        min={1} 
        max={8} 
        step={1}
        bind:value={deepResearchBreadth}
        on:change={() => updateDr('breadth', deepResearchBreadth)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Depth</span>
        <span class="font-mono">{deepResearchDepth}</span>
      </div>
      <RangeSlider 
        name="dr-depth" 
        min={1} 
        max={8} 
        step={1}
        bind:value={deepResearchDepth}
        on:change={() => updateDr('depth', deepResearchDepth)}
      />
    </div>
  </div>
  
  <hr class="!border-t-2" />
  
  <!-- Concurrency -->
  <div class="space-y-2">
    <h4 class="font-semibold text-sm">Concurrency</h4>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Max Concurrent Reports</span>
        <span class="font-mono">{maxConcurrentReports}</span>
      </div>
      <RangeSlider 
        name="max-concurrent" 
        min={1} 
        max={20} 
        step={1}
        bind:value={maxConcurrentReports}
        on:change={() => updateConcurrency('max_concurrent_reports', maxConcurrentReports)}
      />
    </div>
    
    <div class="space-y-1">
      <div class="flex justify-between text-sm">
        <span>Launch Delay (sec)</span>
        <span class="font-mono">{launchDelaySeconds.toFixed(1)}</span>
      </div>
      <RangeSlider 
        name="launch-delay" 
        min={0.1} 
        max={5.0} 
        step={0.1}
        bind:value={launchDelaySeconds}
        on:change={() => updateConcurrency('launch_delay_seconds', launchDelaySeconds)}
      />
    </div>
  </div>
</div>
```

### 5.2.5 Combine & Revise Panel

```svelte
<!-- ui/src/lib/components/config/CombinePanel.svelte -->
<script lang="ts">
  import { SlideToggle } from '@skeletonlabs/skeleton';
  import { configStore } from '$lib/stores/config';
  import { modelCatalog } from '$lib/stores/modelCatalog';
  import ModelCheckboxList from './ModelCheckboxList.svelte';
  
  $: combineEnabled = $configStore.combine?.enabled ?? false;
  $: selectedModels = $configStore.combine?.models?.map(m => `${m.provider}:${m.model}`) ?? [];
  
  function updateCombine(field: string, value: any) {
    configStore.update(cfg => ({
      ...cfg,
      combine: { ...cfg.combine, [field]: value }
    }));
  }
  
  function updateModels(selected: string[]) {
    const models = selected.map(pm => {
      const [provider, model] = pm.split(':');
      return { provider, model };
    });
    updateCombine('models', models);
  }
</script>

<div class="card p-4 space-y-4 h-full">
  <div class="flex items-center justify-between">
    <h3 class="h4">Combine & Revise</h3>
    <SlideToggle 
      name="combine-toggle" 
      size="sm"
      checked={combineEnabled}
      on:change={(e) => updateCombine('enabled', e.target.checked)}
    />
  </div>
  
  {#if combineEnabled}
    <p class="text-sm text-surface-500">
      Select models for the combine/revision step:
    </p>
    
    <ModelCheckboxList 
      models={$modelCatalog.fpf} 
      selected={selectedModels}
      on:change={(e) => updateModels(e.detail)}
    />
  {:else}
    <p class="text-sm text-surface-400 italic">
      Enable to merge outputs from multiple generators into a unified document.
    </p>
  {/if}
</div>
```

### 5.2.6 Runtime Metrics Bar

```svelte
<!-- ui/src/lib/components/config/RuntimeMetrics.svelte -->
<script lang="ts">
  import { ProgressBar } from '@skeletonlabs/skeleton';
  import { configStore } from '$lib/stores/config';
  import { runStore } from '$lib/stores/run';
  
  // Compute expected runs from config
  $: inputFiles = $runStore.inputFileCount ?? 0;
  $: enabledRuns = $configStore.runs?.length ?? 0;
  $: iterations = $configStore.iterations_default ?? 1;
  $: totalReports = inputFiles * enabledRuns * iterations;
  $: completedReports = $runStore.completedReports ?? 0;
  
  $: evalEnabled = $configStore.eval?.enabled ?? false;
  $: evalIterations = $configStore.eval?.iterations ?? 1;
  $: totalEvals = evalEnabled ? totalReports * evalIterations : 0;
  $: completedEvals = $runStore.completedEvals ?? 0;
  
  $: progressPercent = totalReports > 0 
    ? Math.round((completedReports / totalReports) * 100) 
    : 0;
</script>

<div class="card variant-soft p-3">
  <div class="flex items-center gap-6 text-sm">
    <div>
      <span class="text-surface-500">Input Files:</span>
      <span class="font-mono font-bold">{inputFiles}</span>
    </div>
    
    <div>
      <span class="text-surface-500">Total Reports:</span>
      <span class="font-mono font-bold">{completedReports}/{totalReports}</span>
    </div>
    
    <div>
      <span class="text-surface-500">Total Evaluations:</span>
      <span class="font-mono font-bold">{completedEvals}/{totalEvals}</span>
    </div>
    
    <div class="flex-1">
      <ProgressBar value={progressPercent} max={100} meter="bg-primary-500" />
    </div>
  </div>
</div>
```

### 5.2.7 Action Buttons

```svelte
<!-- ui/src/lib/components/config/ActionButtons.svelte -->
<script lang="ts">
  import { Download, FolderOpen, FileText, Save, Play, BarChart } from 'lucide-svelte';
  import { saveConfig, writeConfigToFiles } from '$lib/stores/config';
  import { loadPreset, savePreset } from '$lib/stores/presets';
  import { startGeneration, runEvaluation, runOneFile } from '$lib/api/execution';
  
  let saving = false;
  let running = false;
  
  async function handleWriteConfig() {
    saving = true;
    try {
      await writeConfigToFiles();
    } finally {
      saving = false;
    }
  }
  
  async function handleGenerate() {
    running = true;
    try {
      await startGeneration();
    } finally {
      running = false;
    }
  }
  
  async function handleRunOneFile() {
    running = true;
    try {
      await runOneFile();
    } finally {
      running = false;
    }
  }
  
  async function handleEvaluate() {
    running = true;
    try {
      await runEvaluation();
    } finally {
      running = false;
    }
  }
</script>

<div class="card variant-soft p-3">
  <div class="flex flex-wrap gap-2">
    <!-- Config File Actions -->
    <button class="btn btn-sm variant-ghost" title="Download dependencies">
      <Download size={16} />
      <span>Download</span>
    </button>
    
    <button class="btn btn-sm variant-ghost" title="Open config.yaml">
      <FolderOpen size={16} />
      <span>PM Config</span>
    </button>
    
    <button class="btn btn-sm variant-ghost" title="Open .env file">
      <FileText size={16} />
      <span>.env</span>
    </button>
    
    <div class="border-l border-surface-500 mx-2"></div>
    
    <!-- Preset Actions -->
    <button class="btn btn-sm variant-ghost" on:click={() => loadPreset()}>
      <FolderOpen size={16} />
      <span>Load Preset</span>
    </button>
    
    <button class="btn btn-sm variant-ghost" on:click={() => savePreset()}>
      <Save size={16} />
      <span>Save Preset</span>
    </button>
    
    <div class="border-l border-surface-500 mx-2"></div>
    
    <!-- Write Config -->
    <button 
      class="btn btn-sm variant-filled-secondary" 
      on:click={handleWriteConfig}
      disabled={saving}
    >
      <Save size={16} />
      <span>{saving ? 'Writing...' : 'Write to Configs'}</span>
    </button>
    
    <div class="border-l border-surface-500 mx-2"></div>
    
    <!-- Execution Actions -->
    <button 
      class="btn btn-sm variant-ghost" 
      on:click={handleRunOneFile}
      disabled={running}
    >
      <Play size={16} />
      <span>Run One File</span>
    </button>
    
    <button 
      class="btn btn-sm variant-filled-primary" 
      on:click={handleGenerate}
      disabled={running}
    >
      <Play size={16} />
      <span>{running ? 'Running...' : 'Generate'}</span>
    </button>
    
    <button 
      class="btn btn-sm variant-filled-tertiary" 
      on:click={handleEvaluate}
      disabled={running}
    >
      <BarChart size={16} />
      <span>Evaluate</span>
    </button>
  </div>
</div>
```

### 5.2.8 Preset Selector

```svelte
<!-- ui/src/lib/components/config/PresetSelector.svelte -->
<script lang="ts">
  import { presetsStore, applyPreset } from '$lib/stores/presets';
  
  $: presets = Object.keys($presetsStore);
  let selectedPreset = '';
  
  function handlePresetChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    if (target.value) {
      applyPreset(target.value);
    }
  }
</script>

<div class="flex items-center gap-2">
  <label class="text-sm font-medium">Preset:</label>
  <select 
    class="select w-40"
    bind:value={selectedPreset}
    on:change={handlePresetChange}
  >
    <option value="">-- Select Preset --</option>
    {#each presets as preset}
      <option value={preset}>{preset}</option>
    {/each}
  </select>
</div>
```

### 5.3 Run List Page

```svelte
<!-- ui/src/routes/runs/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus, Filter } from 'lucide-svelte';
  import RunCard from '$lib/components/RunCard.svelte';
  import RunStatusBadge from '$lib/components/RunStatusBadge.svelte';
  import { listRuns } from '$lib/api/runs';
  import type { Run } from '$lib/types/run';
  
  let runs: Run[] = [];
  let loading = true;
  let statusFilter: string | null = null;
  let tagFilter: string = '';
  
  onMount(async () => {
    await loadRuns();
  });
  
  async function loadRuns() {
    loading = true;
    const tags = tagFilter ? [tagFilter] : undefined;
    const response = await listRuns({ status: statusFilter, tags });
    runs = response.runs;
    loading = false;
  }
  
  function handleStatusFilter(status: string | null) {
    statusFilter = status;
    loadRuns();
  }
</script>

<div class="space-y-4">
  <!-- Header -->
  <div class="flex justify-between items-center">
    <h1 class="h2">Runs</h1>
    <button class="btn variant-filled-primary" on:click={() => goto('/runs/new')}>
      <Plus size={18} />
      <span>New Run</span>
    </button>
  </div>
  
  <!-- Filters -->
  <div class="flex gap-2 flex-wrap items-center mb-4">
    <!-- Status Filter -->
    <div class="btn-group variant-soft">
      <button 
        class={statusFilter === null ? 'variant-filled' : ''}
        on:click={() => handleStatusFilter(null)}
      >
        All
      </button>
      {#each ['pending', 'running', 'completed', 'failed'] as status}
        <button 
          class={statusFilter === status ? 'variant-filled' : ''}
          on:click={() => handleStatusFilter(status)}
        >
          {status}
        </button>
      {/each}
    </div>

    <!-- Tag Filter -->
    <input 
        class="input w-48" 
        type="text" 
        placeholder="Filter by tag..." 
        bind:value={tagFilter}
        on:input={() => loadRuns()} 
    />
  </div>
  
  <!-- Run List -->
  {#if loading}
    <div class="flex justify-center p-8">
      <div class="animate-spin">⏳</div>
    </div>
  {:else if runs.length === 0}
    <div class="card p-8 text-center">
      <p class="text-surface-500">No runs found.</p>
      <button class="btn variant-ghost mt-4" on:click={() => goto('/runs/new')}>
        Create your first run
      </button>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {#each runs as run (run.run_id)}
        <RunCard {run} on:click={() => goto(`/runs/${run.run_id}`)} />
      {/each}
    </div>
  {/if}
</div>
```

### 5.3 Run Card Component

```svelte
<!-- ui/src/lib/components/RunCard.svelte -->
<script lang="ts">
  import { formatDistanceToNow } from 'date-fns';
  import { FileText, Clock, Tag } from 'lucide-svelte';
  import RunStatusBadge from './RunStatusBadge.svelte';
  import type { Run } from '$lib/types/run';
  
  export let run: Run;
</script>

<button 
  class="card card-hover p-4 text-left w-full"
  on:click
>
  <div class="flex justify-between items-start mb-2">
    <h3 class="h4 truncate flex-1">{run.title || run.run_id}</h3>
    <RunStatusBadge status={run.status} />
  </div>
  
  <p class="text-sm text-surface-500 mb-3">
    {run.project_id}
  </p>
  
  <div class="flex gap-4 text-xs text-surface-400">
    <span class="flex items-center gap-1">
      <FileText size={14} />
      {run.document_count ?? '?'} docs
    </span>
    <span class="flex items-center gap-1">
      <Clock size={14} />
      {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}
    </span>
  </div>
  
  {#if run.tags.length > 0}
    <div class="flex gap-1 mt-3 flex-wrap">
      {#each run.tags.slice(0, 3) as tag}
        <span class="badge variant-soft text-xs">{tag}</span>
      {/each}
      {#if run.tags.length > 3}
        <span class="badge variant-soft text-xs">+{run.tags.length - 3}</span>
      {/if}
    </div>
  {/if}
</button>
```

### 5.4 Create Run Wizard

```svelte
<!-- ui/src/routes/runs/new/+page.svelte -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { Stepper, Step } from '@skeletonlabs/skeleton';
  import DocumentPicker from '$lib/components/DocumentPicker.svelte';
  import GeneratorConfig from '$lib/components/GeneratorConfig.svelte';
  import EvalConfig from '$lib/components/EvalConfig.svelte';
  import CombineConfig from '$lib/components/CombineConfig.svelte';
  import { createRun } from '$lib/api/runs';
  import type { RunCreateRequest } from '$lib/types/run';
  
  let creating = false;
  let error: string | null = null;
  
  // Form state
  let projectId = 'default';
  let title = '';
  let tagsInput = '';
  let selectedDocuments: string[] = [];
  let generators = {
    fpf: { enabled: true, provider: 'openai', model: 'gpt-5.1', iterations: 1 },
    gptr: { enabled: false, provider: 'google', model: 'gemini-2.5-flash', iterations: 1 },
  };
  let evalConfig = {
    autoRun: true,
    mode: 'both',
    iterations: 1,
    judges: [{ provider: 'openai', model: 'gpt-5.1' }],
  };
  let combineConfig = {
    enabled: true,
    model: { provider: 'openai', model: 'gpt-5.1' },
  };
  
  async function handleSubmit() {
    creating = true;
    error = null;
    
    try {
      const request: RunCreateRequest = {
        project_id: projectId,
        title: title || undefined,
        tags: tagsInput.split(',').map(t => t.trim()).filter(t => t),
        documents: selectedDocuments.map(id => ({ document_id: id })),
        config: {
          generators: Object.entries(generators)
            .filter(([_, g]) => g.enabled)
            .map(([type, g]) => ({
              type,
              provider: g.provider,
              model: g.model,
              iterations: g.iterations,
            })),
          eval: evalConfig,
          combine: combineConfig,
        },
      };
      
      const run = await createRun(request);
      goto(`/runs/${run.run_id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create run';
    } finally {
      creating = false;
    }
  }
</script>

<div class="max-w-3xl mx-auto">
  <h1 class="h2 mb-6">Create New Run</h1>
  
  {#if error}
    <aside class="alert variant-filled-error mb-4">
      <p>{error}</p>
    </aside>
  {/if}
  
  <Stepper on:complete={handleSubmit}>
    <!-- Step 1: Basic Info -->
    <Step>
      <svelte:fragment slot="header">Basic Info</svelte:fragment>
      
      <label class="label">
        <span>Project</span>
        <select class="select" bind:value={projectId}>
          <option value="default">Default Project</option>
          <option value="firstpub-platform">FirstPub Platform</option>
        </select>
      </label>
      
      <label class="label mt-4">
        <span>Title (optional)</span>
        <input 
          class="input" 
          type="text" 
          placeholder="e.g., Q4 EO Analysis"
          bind:value={title}
        />
      </label>

      <label class="label mt-4">
        <span>Tags (comma separated)</span>
        <input 
          class="input" 
          type="text" 
          placeholder="e.g., Q4, Report, Draft"
          bind:value={tagsInput}
        />
      </label>
    </Step>
    
    <!-- Step 2: Documents -->
    <Step>
      <svelte:fragment slot="header">Select Documents</svelte:fragment>
      <DocumentPicker bind:selected={selectedDocuments} />
    </Step>
    
    <!-- Step 3: Generators -->
    <Step>
      <svelte:fragment slot="header">Generator Configuration</svelte:fragment>
      <GeneratorConfig bind:config={generators} />
    </Step>
    
    <!-- Step 4: Evaluation -->
    <Step>
      <svelte:fragment slot="header">Evaluation Settings</svelte:fragment>
      <EvalConfig bind:config={evalConfig} />
    </Step>
    
    <!-- Step 5: Combine -->
    <Step>
      <svelte:fragment slot="header">Combine Settings</svelte:fragment>
      <CombineConfig bind:config={combineConfig} />
    </Step>
    
    <!-- Step 6: Review -->
    <Step>
      <svelte:fragment slot="header">Review & Create</svelte:fragment>
      
      <div class="card p-4 space-y-4">
        <div>
          <span class="font-bold">Project:</span> {projectId}
        </div>
        <div>
          <span class="font-bold">Title:</span> {title || '(none)'}
        </div>
        <div>
          <span class="font-bold">Documents:</span> {selectedDocuments.length} selected
        </div>
        <div>
          <span class="font-bold">Generators:</span>
          {Object.entries(generators).filter(([_, g]) => g.enabled).map(([t]) => t).join(', ')}
        </div>
        <div>
          <span class="font-bold">Eval:</span> {evalConfig.mode}, {evalConfig.iterations} iterations
        </div>
        <div>
          <span class="font-bold">Combine:</span> {combineConfig.enabled ? 'Enabled' : 'Disabled'}
        </div>
      </div>
    </Step>
  </Stepper>
</div>
```

### 5.5 Document Picker Component

```svelte
<!-- ui/src/lib/components/DocumentPicker.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { Search, Folder, FileText, Check } from 'lucide-svelte';
  import { listDocuments, searchGitHubRepo } from '$lib/api/documents';
  import type { Document } from '$lib/types/document';
  
  export let selected: string[] = [];
  
  let mode: 'recent' | 'github' = 'recent';
  let searchQuery = '';
  let recentDocuments: Document[] = [];
  let githubResults: { path: string; type: 'file' | 'dir' }[] = [];
  let loading = false;
  
  // GitHub browser state
  let githubRepo = '';
  let githubPath = '';
  let githubRef = 'main';
  
  onMount(async () => {
    const response = await listDocuments({ limit: 20 });
    recentDocuments = response.documents;
  });
  
  async function browseGitHub() {
    loading = true;
    githubResults = await searchGitHubRepo(githubRepo, githubPath, githubRef);
    loading = false;
  }
  
  function toggleDocument(docId: string) {
    if (selected.includes(docId)) {
      selected = selected.filter(id => id !== docId);
    } else {
      selected = [...selected, docId];
    }
  }
  
  function selectAll(docs: Document[]) {
    const ids = docs.map(d => d.document_id);
    selected = [...new Set([...selected, ...ids])];
  }
</script>

<div class="space-y-4">
  <!-- Mode Toggle -->
  <div class="btn-group variant-ghost">
    <button 
      class:variant-filled={mode === 'recent'}
      on:click={() => mode = 'recent'}
    >
      Recent Documents
    </button>
    <button 
      class:variant-filled={mode === 'github'}
      on:click={() => mode = 'github'}
    >
      Browse GitHub
    </button>
  </div>
  
  {#if mode === 'recent'}
    <!-- Recent Documents -->
    <div class="input-group">
      <div class="input-group-shim"><Search size={18} /></div>
      <input type="text" placeholder="Filter documents..." bind:value={searchQuery} />
    </div>
    
    <div class="space-y-2 max-h-64 overflow-y-auto">
      {#each recentDocuments.filter(d => 
        !searchQuery || d.display_name?.toLowerCase().includes(searchQuery.toLowerCase())
      ) as doc (doc.document_id)}
        <button
          class="card p-3 w-full text-left flex items-center gap-3"
          class:variant-filled-primary={selected.includes(doc.document_id)}
          on:click={() => toggleDocument(doc.document_id)}
        >
          {#if selected.includes(doc.document_id)}
            <Check size={18} class="text-primary-500" />
          {:else}
            <FileText size={18} />
          {/if}
          <span class="flex-1 truncate">{doc.display_name}</span>
        </button>
      {/each}
    </div>
    
  {:else}
    <!-- GitHub Browser -->
    <div class="grid grid-cols-3 gap-2">
      <input 
        class="input col-span-2" 
        placeholder="owner/repo" 
        bind:value={githubRepo}
      />
      <input 
        class="input" 
        placeholder="branch" 
        bind:value={githubRef}
      />
    </div>
    
    <div class="input-group">
      <input 
        class="input" 
        placeholder="path (e.g., docs/)" 
        bind:value={githubPath}
      />
      <button class="variant-filled-primary" on:click={browseGitHub}>
        Browse
      </button>
    </div>
    
    {#if loading}
      <p class="text-center p-4">Loading...</p>
    {:else}
      <div class="space-y-2 max-h-64 overflow-y-auto">
        {#each githubResults as item}
          <button
            class="card p-3 w-full text-left flex items-center gap-3"
            on:click={() => {
              if (item.type === 'dir') {
                githubPath = item.path + '/';
                browseGitHub();
              } else {
                // Register and select document
                // (handled by API call)
              }
            }}
          >
            {#if item.type === 'dir'}
              <Folder size={18} />
            {:else}
              <FileText size={18} />
            {/if}
            <span class="flex-1 truncate">{item.path}</span>
          </button>
        {/each}
      </div>
    {/if}
  {/if}
  
  <!-- Selection Summary -->
  <div class="card variant-soft p-3">
    <span class="font-bold">{selected.length}</span> documents selected
  </div>
</div>
```

### 5.6 Combine Interface

The Combine interface allows users to merge artifacts from a completed run.

**Location:** `ui/src/routes/runs/[run_id]/combine/+page.svelte`

**Features:**
- **Artifact Selection:** Checkbox list of artifacts to include (default: all top-rated).
- **Strategy Config:** Dropdown for strategy (Concatenate, Best-of-N, etc.).
- **Preview:** Show order of artifacts.
- **Action:** "Combine Artifacts" button triggers API.

**Component Structure:**
```svelte
<script>
  let selectedArtifacts = [];
  let strategy = 'concatenate';
  let config = { separator: '\n\n---\n\n', include_toc: true };
</script>

<div class="card p-4">
  <h3 class="h3">Combine Artifacts</h3>
  
  <!-- Strategy Selection -->
  <label class="label">
    <span>Strategy</span>
    <select class="select" bind:value={strategy}>
      <option value="concatenate">Concatenate</option>
      <option value="best_of_n">Best of N</option>
      <option value="section_assembly">Section Assembly</option>
    </select>
  </label>
  
  <!-- Artifact Selection -->
  <div class="list-box">
    {#each artifacts as artifact}
      <label class="flex items-center space-x-2">
        <input type="checkbox" class="checkbox" bind:group={selectedArtifacts} value={artifact.id} />
        <span>{artifact.document.display_name} ({artifact.metadata.model}) - Score: {artifact.score}</span>
      </label>
    {/each}
  </div>
  
  <button class="btn variant-filled-primary" on:click={handleCombine}>
    Combine Selected
  </button>
</div>
```

## 6. API Client

### 6.1 Base Client

```typescript
// ui/src/lib/api/client.ts
const API_BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      error.code || 'UNKNOWN_ERROR',
      error.message || `HTTP ${response.status}`,
    );
  }
  
  return response.json();
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path, { method: 'GET' }),
  
  post: <T>(path: string, body: unknown) =>
    apiRequest<T>(path, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  
  patch: <T>(path: string, body: unknown) =>
    apiRequest<T>(path, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  
  delete: <T>(path: string) => apiRequest<T>(path, { method: 'DELETE' }),
};
```

### 6.2 Run API

```typescript
// ui/src/lib/api/runs.ts
import { api } from './client';
import type { Run, RunCreateRequest, RunListResponse, RunUpdateRequest } from '$lib/types/run';

export async function listRuns(params?: {
  status?: string | null;
  project_id?: string;
  limit?: number;
  offset?: number;
}): Promise<RunListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.project_id) query.set('project_id', params.project_id);
  if (params?.limit) query.set('limit', params.limit.toString());
  if (params?.offset) query.set('offset', params.offset.toString());
  
  const queryStr = query.toString();
  return api.get(`/runs${queryStr ? '?' + queryStr : ''}`);
}

export async function getRun(runId: string): Promise<Run> {
  return api.get(`/runs/${runId}`);
}

export async function createRun(request: RunCreateRequest): Promise<Run> {
  return api.post('/runs', request);
}

export async function updateRun(runId: string, request: RunUpdateRequest): Promise<Run> {
  return api.patch(`/runs/${runId}`, request);
}

export async function cancelRun(runId: string): Promise<Run> {
  return api.post(`/runs/${runId}/cancel`, {});
}

export async function deleteRun(runId: string): Promise<void> {
  return api.delete(`/runs/${runId}`);
}
```

### 6.3 Type Definitions

```typescript
// ui/src/lib/types/run.ts
export type RunStatus = 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
export type GeneratorType = 'fpf' | 'gptr' | 'dr' | 'ma';
export type EvalMode = 'single' | 'pairwise' | 'both';
export type EffortLevel = 'low' | 'medium' | 'high';

export interface Run {
  run_id: string;
  project_id: string;
  title: string | null;
  status: RunStatus;
  priority: number;
  config: RunConfig;
  tags: string[];
  requested_by: string;
  summary: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  document_count?: number;
}

export interface RunConfig {
  // General settings
  iterations_default: number;
  one_file_only: boolean;
  follow_guidelines: boolean;
  
  // Path settings
  input_folder: string;
  output_folder: string;
  instructions_file: string;
  guidelines_file: string;
  
  // Generator enable flags
  enable: GeneratorEnables;
  
  // Run definitions (which models to use)
  runs: GeneratorRun[];
  
  // FPF-specific parameters
  fpf: FpfConfig;
  
  // GPTR-specific parameters
  gptr: GptrConfig;
  
  // DR-specific parameters
  dr: DrConfig;
  
  // Concurrency settings
  concurrency: ConcurrencyConfig;
  
  // Evaluation settings
  eval: EvalConfig;
  
  // Combine settings
  combine: CombineConfig;
  
  // Repository references (for GitHub-backed workflows)
  docs_repo: string | null;
  outputs_repo: string | null;
  logs_repo: string | null;
}

export interface GeneratorEnables {
  fpf: boolean;
  gptr: boolean;
  dr: boolean;
  ma: boolean;
}

export interface GeneratorRun {
  type: GeneratorType;
  provider: string;
  model: string;
  iterations?: number;  // Override iterations_default for this run
}

export interface FpfConfig {
  grounding_max_results: number;      // 1-10, default 3
  max_tokens: number;                 // 1000-200000, default 50000
  reasoning_effort: EffortLevel;      // low/medium/high
  web_search_context_size: EffortLevel;  // low/medium/high
}

export interface GptrConfig {
  // Token limits
  fast_token_limit: number;           // 3000-87538
  smart_token_limit: number;          // 6000-175038
  strategic_token_limit: number;      // 4000-87538
  browse_chunk_max_length: number;    // 8192-26262
  summary_token_limit: number;        // 700-1759
  
  // Research parameters
  temperature: number;                // 0.0-1.0
  max_search_results_per_query: number;  // 1-8
  total_words: number;                // 1200-43762
  max_iterations: number;             // 1-8
  max_subtopics: number;              // 1-9
}

export interface DrConfig {
  breadth: number;                    // 1-8 (DEEP_RESEARCH_BREADTH)
  depth: number;                      // 1-8 (DEEP_RESEARCH_DEPTH)
}

export interface ConcurrencyConfig {
  max_concurrent_reports: number;     // 1-20, default 11
  launch_delay_seconds: number;       // 0.1-5.0, default 0.5
}

export interface EvalConfig {
  enabled: boolean;
  auto_run: boolean;
  iterations: number;                 // 1-9
  pairwise_top_n: number;             // 1-10
  mode: EvalMode;                     // single/pairwise/both
  judges: ProviderModel[];
  output_directory: string;
  export_directory: string;
  log: LogConfig;
}

export interface LogConfig {
  console_level: EffortLevel;
  file_level: EffortLevel;
}

export interface CombineConfig {
  enabled: boolean;
  models: ProviderModel[];
}

export interface ProviderModel {
  provider: string;
  model: string;
}

export interface RunCreateRequest {
  project_id: string;
  title?: string;
  config?: Partial<RunConfig>;
  tags?: string[];
  priority?: number;
  documents?: DocumentAttachment[];
}

export interface DocumentAttachment {
  document_id?: string;
  repository?: string;
  path?: string;
  ref?: string;
  content?: string;
  filename?: string;
}

export interface RunUpdateRequest {
  title?: string;
  priority?: number;
  tags?: string[];
  summary?: string;
}

export interface RunListResponse {
  runs: Run[];
  total: number;
  limit: number;
  offset: number;
}

// ui/src/lib/types/config.ts
export interface ModelCatalog {
  fpf: string[];    // ["openai:gpt-5.1", "google:gemini-2.5-flash", ...]
  gptr: string[];
  dr: string[];
  ma: string[];
}

export interface Preset {
  name: string;
  config: Partial<RunConfig>;
}

export interface PresetsMap {
  [name: string]: Partial<RunConfig>;
}
```

### 6.4 Svelte Stores (State Management)

#### 6.4.1 Config Store

```typescript
// ui/src/lib/stores/config.ts
import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import type { RunConfig } from '$lib/types/run';

// Default configuration matching ACM 1.0 defaults
const defaultConfig: RunConfig = {
  iterations_default: 1,
  one_file_only: false,
  follow_guidelines: false,
  input_folder: '',
  output_folder: '',
  instructions_file: '',
  guidelines_file: '',
  enable: { fpf: true, gptr: true, dr: true, ma: true },
  runs: [],
  fpf: {
    grounding_max_results: 3,
    max_tokens: 50000,
    reasoning_effort: 'medium',
    web_search_context_size: 'medium',
  },
  gptr: {
    fast_token_limit: 8000,
    smart_token_limit: 16000,
    strategic_token_limit: 8000,
    browse_chunk_max_length: 8192,
    summary_token_limit: 700,
    temperature: 0.4,
    max_search_results_per_query: 4,
    total_words: 8000,
    max_iterations: 3,
    max_subtopics: 3,
  },
  dr: {
    breadth: 3,
    depth: 2,
  },
  concurrency: {
    max_concurrent_reports: 11,
    launch_delay_seconds: 0.5,
  },
  eval: {
    enabled: true,
    auto_run: true,
    iterations: 1,
    pairwise_top_n: 3,
    mode: 'both',
    judges: [],
    output_directory: 'gptr-eval-process/final_reports',
    export_directory: 'gptr-eval-process/exports',
    log: { console_level: 'medium', file_level: 'medium' },
  },
  combine: {
    enabled: false,
    models: [],
  },
  docs_repo: null,
  outputs_repo: null,
  logs_repo: null,
};

export const configStore = writable<RunConfig>(defaultConfig);

export async function loadConfig(): Promise<void> {
  try {
    const config = await api.get<RunConfig>('/config');
    configStore.set({ ...defaultConfig, ...config });
  } catch (e) {
    console.warn('Failed to load config, using defaults:', e);
    configStore.set(defaultConfig);
  }
}

export async function saveConfig(): Promise<void> {
  const config = await new Promise<RunConfig>(resolve => {
    configStore.subscribe(c => resolve(c))();
  });
  await api.post('/config', config);
}

export async function writeConfigToFiles(): Promise<void> {
  // Writes current config to all ACM config files (config.yaml, fpf_config.yaml, etc.)
  await api.post('/config/write-files', {});
}
```

#### 6.4.2 Presets Store

```typescript
// ui/src/lib/stores/presets.ts
import { writable, get } from 'svelte/store';
import { api } from '$lib/api/client';
import { configStore } from './config';
import type { PresetsMap, RunConfig } from '$lib/types/run';

export const presetsStore = writable<PresetsMap>({});

export async function loadPresets(): Promise<void> {
  try {
    const presets = await api.get<PresetsMap>('/presets');
    presetsStore.set(presets);
  } catch (e) {
    console.warn('Failed to load presets:', e);
    presetsStore.set({});
  }
}

export async function applyPreset(name: string): Promise<void> {
  const presets = get(presetsStore);
  const preset = presets[name];
  if (preset) {
    configStore.update(cfg => ({ ...cfg, ...preset }));
  }
}

export async function savePreset(name?: string): Promise<void> {
  const presetName = name || prompt('Preset name:');
  if (!presetName) return;
  
  const config = get(configStore);
  await api.post(`/presets/${presetName}`, config);
  await loadPresets();
}

export async function loadPreset(name?: string): Promise<void> {
  const presetName = name || prompt('Preset name to load:');
  if (!presetName) return;
  await applyPreset(presetName);
}
```

#### 6.4.3 Model Catalog Store

```typescript
// ui/src/lib/stores/modelCatalog.ts
import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import type { ModelCatalog } from '$lib/types/config';

const defaultCatalog: ModelCatalog = {
  fpf: [],
  gptr: [],
  dr: [],
  ma: [],
};

export const modelCatalog = writable<ModelCatalog>(defaultCatalog);

export async function loadModelCatalog(): Promise<void> {
  try {
    const catalog = await api.get<ModelCatalog>('/models/catalog');
    modelCatalog.set(catalog);
  } catch (e) {
    console.warn('Failed to load model catalog:', e);
    modelCatalog.set(defaultCatalog);
  }
}
```

#### 6.4.4 Run State Store (for metrics)

```typescript
// ui/src/lib/stores/run.ts
import { writable } from 'svelte/store';

interface RunState {
  inputFileCount: number;
  completedReports: number;
  completedEvals: number;
  isRunning: boolean;
  currentPhase: string | null;
}

const defaultRunState: RunState = {
  inputFileCount: 0,
  completedReports: 0,
  completedEvals: 0,
  isRunning: false,
  currentPhase: null,
};

export const runStore = writable<RunState>(defaultRunState);

export function updateRunProgress(updates: Partial<RunState>): void {
  runStore.update(state => ({ ...state, ...updates }));
}
```

### 6.5 Execution API

```typescript
// ui/src/lib/api/execution.ts
import { api } from './client';
import { runStore, updateRunProgress } from '$lib/stores/run';

export async function startGeneration(): Promise<void> {
  updateRunProgress({ isRunning: true, currentPhase: 'generation' });
  try {
    await api.post('/execute/generate', {});
  } finally {
    updateRunProgress({ isRunning: false, currentPhase: null });
  }
}

export async function runOneFile(): Promise<void> {
  updateRunProgress({ isRunning: true, currentPhase: 'generation' });
  try {
    await api.post('/execute/generate', { one_file_only: true });
  } finally {
    updateRunProgress({ isRunning: false, currentPhase: null });
  }
}

export async function runEvaluation(): Promise<void> {
  updateRunProgress({ isRunning: true, currentPhase: 'evaluation' });
  try {
    await api.post('/execute/evaluate', {});
  } finally {
    updateRunProgress({ isRunning: false, currentPhase: null });
  }
}
```

## 7. Build & Development Commands

### 7.1 package.json Scripts

```json
{
  "name": "acm2-ui",
  "version": "2.0.0",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "lint": "eslint .",
    "format": "prettier --write ."
  },
  "devDependencies": {
    "@skeletonlabs/skeleton": "^2.10.0",
    "@skeletonlabs/tw-plugin": "^0.4.0",
    "@sveltejs/adapter-static": "^3.0.0",
    "@sveltejs/kit": "^2.5.0",
    "@sveltejs/vite-plugin-svelte": "^3.0.0",
    "autoprefixer": "^10.4.0",
    "lucide-svelte": "^0.400.0",
    "postcss": "^8.4.0",
    "svelte": "^5.0.0",
    "svelte-check": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  },
  "dependencies": {
    "date-fns": "^3.6.0"
  }
}
```

### 7.2 Development Workflow

```bash
# Terminal 1: Start backend
cd acm2
acm2 serve --dev --port 8000

# Terminal 2: Start frontend with hot reload
cd acm2/ui
npm install
npm run dev

# Open browser to http://localhost:5173
```

### 7.3 Production Build

```bash
# Build frontend
cd acm2/ui
npm run build

# Start production server (serves both API and UI)
cd acm2
acm2 serve --port 8000

# Open browser to http://localhost:8000
```

## 8. SaaS Considerations

### 8.1 Authentication (Future)

When adding auth for SaaS:

1. **Add auth provider selection** to settings:
   ```svelte
   <!-- Login page will appear when AUTH_ENABLED=true -->
   {#if $authRequired && !$user}
     <LoginPage />
   {:else}
     <slot />
   {/if}
   ```

2. **API client adds auth header**:
   ```typescript
   // ui/src/lib/api/client.ts
   const token = getAuthToken();
   headers: {
     'Authorization': token ? `Bearer ${token}` : undefined,
     ...
   }
   ```

3. **Backend validates token** and injects `tenant_id` into all queries.

### 8.2 CDN Deployment (Future)

For SaaS, deploy frontend separately:

1. Build static files: `npm run build`
2. Upload `ui/dist/` to CloudFront/Vercel/Netlify
3. Configure SPA fallback (all routes → index.html)
4. Set API base URL via environment variable:
   ```typescript
   const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
   ```

## 9. Success Criteria

### 9.1 Core Functionality

| Criteria | Verification |
|----------|--------------|
| Dev server starts | `npm run dev` starts without errors |
| Production build | `npm run build` creates `dist/` folder |
| FastAPI serves UI | `localhost:8000/` shows the app |
| Run list loads | Runs displayed from API |
| Create run works | New run appears in list |
| Run detail loads | Shows documents, status, progress |
| Settings persist | API keys saved to localStorage |
| Responsive layout | Works on 1024px+ screens |

### 9.2 ACM 1.0 Parity Requirements

| Category | Requirement | Verification |
|----------|-------------|--------------|
| **Providers Panel** | 4 generator sections (FPF, GPTR, DR, MA) | All 4 groupboxes render with enable toggles |
| **Providers Panel** | Model checkboxes per generator | Checkboxes populate from model catalog API |
| **Providers Panel** | Multi-select models | Can select multiple models per generator |
| **Paths Panel** | 4 path inputs with Browse/Open | input_folder, output_folder, instructions, guidelines |
| **Paths Panel** | Follow Guidelines checkbox | Checkbox persists to config |
| **Eval Panel** | Enable/disable toggle | Group can be collapsed |
| **Eval Panel** | Auto-run checkbox | Maps to `eval.auto_run` |
| **Eval Panel** | Mode dropdown | single/pairwise/both options |
| **Eval Panel** | Iterations slider | Range 1-9 |
| **Eval Panel** | Pairwise Top-N slider | Range 1-10 |
| **Eval Panel** | Judge model checkboxes | Multi-select from model catalog |
| **Eval Panel** | Output/Export dir inputs | Editable path fields |
| **Params Panel** | General iterations slider | Range 1-9 |
| **Params Panel** | FPF grounding slider | Range 1-10 |
| **Params Panel** | FPF max tokens slider | Range 1K-200K |
| **Params Panel** | FPF reasoning effort dropdown | low/medium/high |
| **Params Panel** | FPF web search context dropdown | low/medium/high |
| **Params Panel** | GPTR fast token slider | Range 3K-87K |
| **Params Panel** | GPTR smart token slider | Range 6K-175K |
| **Params Panel** | GPTR strategic token slider | Range 4K-87K |
| **Params Panel** | GPTR browse chunk slider | Range 8K-26K |
| **Params Panel** | GPTR summary token slider | Range 700-1759 |
| **Params Panel** | GPTR temperature slider | Range 0.0-1.0 (displayed as 0-100) |
| **Params Panel** | GPTR max search results slider | Range 1-8 |
| **Params Panel** | GPTR total words slider | Range 1200-43762 |
| **Params Panel** | GPTR max iterations slider | Range 1-8 |
| **Params Panel** | GPTR max subtopics slider | Range 1-9 |
| **Params Panel** | DR breadth slider | Range 1-8 |
| **Params Panel** | DR depth slider | Range 1-8 |
| **Params Panel** | Concurrency max concurrent slider | Range 1-20 |
| **Params Panel** | Concurrency launch delay slider | Range 0.1-5.0 |
| **Combine Panel** | Enable toggle | Maps to `combine.enabled` |
| **Combine Panel** | Model checkboxes | Multi-select for combine models |
| **Presets** | Preset dropdown selector | Loads from presets API |
| **Presets** | Load preset button | Applies preset to all fields |
| **Presets** | Save preset button | Saves current config as preset |
| **Metrics Bar** | Input file count | Shows count from input folder |
| **Metrics Bar** | Reports progress | Shows completed/total |
| **Metrics Bar** | Evaluations progress | Shows completed/total |
| **Metrics Bar** | Progress bar | Visual progress indicator |
| **Action Buttons** | Write to Configs | Saves to all config files |
| **Action Buttons** | Run One File | Executes with one_file_only=true |
| **Action Buttons** | Generate | Starts full generation |
| **Action Buttons** | Evaluate | Runs evaluation only |

### 9.3 Total Control Count

The GUI must implement **at minimum**:

| Control Type | Count | Source |
|--------------|-------|--------|
| Sliders | 20 | As listed in Section 5.0.1 |
| Checkboxes | 15+ | Generator enables, model selections, eval options |
| Dropdowns | 6 | Presets, reasoning effort, web search, eval mode, log levels |
| Path Inputs | 6 | Paths + eval dirs |
| Text Inputs | 2 | Tags, title |
| Action Buttons | 10 | Load/Save preset, Write config, Run one, Generate, Evaluate, etc. |

## 10. Next Steps

After Step 11 (GUI):
- **Step 12**: CLI implementation (mirrors GUI functionality)
- **Step 13**: Generator adapters (FPF, GPTR, DR, MA)
- **Step 14**: Evaluation pipeline integration
- **Step 15**: Real-time progress updates (WebSocket or SSE)
