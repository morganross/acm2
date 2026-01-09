import { DollarSign, Zap, Scale } from 'lucide-react'

// Static FPF Generation Models Data - Matches GUI exactly (54 models, excluding DR Native)
const FPF_MODELS = [
  // Anthropic Models
  { provider: 'Anthropic', model: 'anthropic/claude-3-5-haiku', input: '$0.80', output: '$4.00', avg1k: '$0.0024' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-7-sonnet', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-haiku-4-5', input: '$1.00', output: '$5.00', avg1k: '$0.0030' },
  { provider: 'Anthropic', model: 'anthropic/claude-opus-4-5', input: '$5.00', output: '$25.00', avg1k: '$0.0150' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4-5', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  
  // Google Models
  { provider: 'Google', model: 'google/gemini-2.5-flash', input: '$0.30', output: '$2.50', avg1k: '$0.0014' },
  { provider: 'Google', model: 'google/gemini-2.5-flash-lite', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'Google', model: 'google/gemini-2.5-pro', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-3-flash-preview', input: '$0.50', output: '$3.00', avg1k: '$0.0018' },
  { provider: 'Google', model: 'google/gemini-3-pro-preview', input: '$2.00', output: '$12.00', avg1k: '$0.0070' },
  
  // OpenAI GPT Series
  { provider: 'OpenAI', model: 'openai/gpt-4.1', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-mini', input: '$0.40', output: '$1.60', avg1k: '$0.0010' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-nano', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'OpenAI', model: 'openai/gpt-5', input: '$0.63', output: '$5.00', avg1k: '$0.0028' },
  { provider: 'OpenAI', model: 'openai/gpt-5-mini', input: '$0.25', output: '$2.00', avg1k: '$0.0011' },
  { provider: 'OpenAI', model: 'openai/gpt-5-nano', input: '$0.05', output: '$0.40', avg1k: '$0.0002' },
  { provider: 'OpenAI', model: 'openai/gpt-5.1', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5.2', input: '$1.75', output: '$14.00', avg1k: '$0.0088' },
  
  // OpenAI o-Series (Reasoning)
  { provider: 'OpenAI', model: 'openai/o3', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/o4-mini', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  
  // OpenRouter Paid Models
  { provider: 'OpenRouter', model: 'openrouter/deepseek/deepseek-r1', input: '$0.70', output: '$2.40', avg1k: '$0.0016' },
  { provider: 'OpenRouter', model: 'openrouter/meta-llama/llama-3.1-405b-instruct', input: '$2.00', output: '$2.00', avg1k: '$0.0020' },
  { provider: 'OpenRouter', model: 'openrouter/meta-llama/llama-3.1-70b-instruct', input: '$0.40', output: '$0.40', avg1k: '$0.0004' },
  { provider: 'OpenRouter', model: 'openrouter/mistralai/mistral-large-2411', input: '$2.00', output: '$6.00', avg1k: '$0.0040' },
  { provider: 'OpenRouter', model: 'openrouter/mistralai/mistral-small-3.1-24b-instruct', input: '$0.10', output: '$0.30', avg1k: '$0.0002' },
  { provider: 'OpenRouter', model: 'openrouter/openai/gpt-4o', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenRouter', model: 'openrouter/openai/gpt-4o-mini', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenRouter', model: 'openrouter/perplexity/sonar', input: '$1.00', output: '$1.00', avg1k: '$0.0010' },
  { provider: 'OpenRouter', model: 'openrouter/perplexity/sonar-pro', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'OpenRouter', model: 'openrouter/perplexity/sonar-reasoning-pro', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  
  // OpenRouter FREE Models
  { provider: 'OpenRouter FREE', model: 'allenai/olmo-3-32b-think', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'allenai/olmo-3.1-32b-think', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'arcee-ai/trinity-mini', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'deepseek/deepseek-r1-0528', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemini-2.0-flash-exp', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemma-3-27b-it', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemma-3n-e2b-it', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemma-3n-e4b-it', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'kwaipilot/kat-coder-pro', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'meta-llama/llama-3.1-405b-instruct', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'meta-llama/llama-3.2-3b-instruct', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'meta-llama/llama-3.3-70b-instruct', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'mistralai/devstral-2512', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'mistralai/mistral-small-3.1-24b-instruct', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nex-agi/deepseek-v3.1-nex-n1', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nousresearch/hermes-3-llama-3.1-405b', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nvidia/nemotron-nano-12b-v2-vl', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nvidia/nemotron-nano-9b-v2', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'qwen/qwen3-coder', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'tngtech/deepseek-r1t-chimera', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'tngtech/deepseek-r1t2-chimera', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'tngtech/tng-r1t-chimera', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'xiaomi/mimo-v2-flash', input: 'Free', output: 'Free', avg1k: '$0.0000' },
]

// Static Evaluation Judge Models Data - Same as generation models (used as judges for evaluation)
const EVAL_MODELS = [
  // Anthropic Models
  { provider: 'Anthropic', model: 'anthropic/claude-3-5-haiku (judge)', input: '$0.80', output: '$4.00', avg1k: '$0.0024' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-7-sonnet (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-haiku-4-5 (judge)', input: '$1.00', output: '$5.00', avg1k: '$0.0030' },
  { provider: 'Anthropic', model: 'anthropic/claude-opus-4-5 (judge)', input: '$5.00', output: '$25.00', avg1k: '$0.0150' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4 (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4-5 (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  
  // Google Models
  { provider: 'Google', model: 'google/gemini-2.5-flash (judge)', input: '$0.30', output: '$2.50', avg1k: '$0.0014' },
  { provider: 'Google', model: 'google/gemini-2.5-flash-lite (judge)', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'Google', model: 'google/gemini-2.5-pro (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-3-flash-preview (judge)', input: '$0.50', output: '$3.00', avg1k: '$0.0018' },
  { provider: 'Google', model: 'google/gemini-3-pro-preview (judge)', input: '$2.00', output: '$12.00', avg1k: '$0.0070' },
  
  // OpenAI GPT Series
  { provider: 'OpenAI', model: 'openai/gpt-4.1 (judge)', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-mini (judge)', input: '$0.40', output: '$1.60', avg1k: '$0.0010' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-nano (judge)', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'OpenAI', model: 'openai/gpt-5 (judge)', input: '$0.63', output: '$5.00', avg1k: '$0.0028' },
  { provider: 'OpenAI', model: 'openai/gpt-5-mini (judge)', input: '$0.25', output: '$2.00', avg1k: '$0.0011' },
  { provider: 'OpenAI', model: 'openai/gpt-5-nano (judge)', input: '$0.05', output: '$0.40', avg1k: '$0.0002' },
  { provider: 'OpenAI', model: 'openai/gpt-5.1 (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5.2 (judge)', input: '$1.75', output: '$14.00', avg1k: '$0.0088' },
  
  // OpenAI o-Series (Reasoning)
  { provider: 'OpenAI', model: 'openai/o3 (judge)', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/o4-mini (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  
  // OpenRouter Paid Models
  { provider: 'OpenRouter', model: 'openrouter/deepseek/deepseek-r1 (judge)', input: '$0.70', output: '$2.40', avg1k: '$0.0016' },
  { provider: 'OpenRouter', model: 'openrouter/meta-llama/llama-3.1-405b-instruct (judge)', input: '$2.00', output: '$2.00', avg1k: '$0.0020' },
  { provider: 'OpenRouter', model: 'openrouter/meta-llama/llama-3.1-70b-instruct (judge)', input: '$0.40', output: '$0.40', avg1k: '$0.0004' },
  { provider: 'OpenRouter', model: 'openrouter/mistralai/mistral-large-2411 (judge)', input: '$2.00', output: '$6.00', avg1k: '$0.0040' },
  { provider: 'OpenRouter', model: 'openrouter/mistralai/mistral-small-3.1-24b-instruct (judge)', input: '$0.10', output: '$0.30', avg1k: '$0.0002' },
  { provider: 'OpenRouter', model: 'openrouter/openai/gpt-4o (judge)', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenRouter', model: 'openrouter/openai/gpt-4o-mini (judge)', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenRouter', model: 'openrouter/perplexity/sonar (judge)', input: '$1.00', output: '$1.00', avg1k: '$0.0010' },
  { provider: 'OpenRouter', model: 'openrouter/perplexity/sonar-pro (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'OpenRouter', model: 'openrouter/perplexity/sonar-reasoning-pro (judge)', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  
  // OpenRouter FREE Models
  { provider: 'OpenRouter FREE', model: 'allenai/olmo-3-32b-think (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'allenai/olmo-3.1-32b-think (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'arcee-ai/trinity-mini (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'deepseek/deepseek-r1-0528 (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemini-2.0-flash-exp (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemma-3-27b-it (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemma-3n-e2b-it (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'google/gemma-3n-e4b-it (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'kwaipilot/kat-coder-pro (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'meta-llama/llama-3.1-405b-instruct (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'meta-llama/llama-3.2-3b-instruct (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'meta-llama/llama-3.3-70b-instruct (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'mistralai/devstral-2512 (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'mistralai/mistral-small-3.1-24b-instruct (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nex-agi/deepseek-v3.1-nex-n1 (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nousresearch/hermes-3-llama-3.1-405b (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nvidia/nemotron-nano-12b-v2-vl (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'nvidia/nemotron-nano-9b-v2 (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'qwen/qwen3-coder (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'tngtech/deepseek-r1t-chimera (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'tngtech/deepseek-r1t2-chimera (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'tngtech/tng-r1t-chimera (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'xiaomi/mimo-v2-flash (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
]

export default function Ratings() {

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="border-b pb-6">
        <div className="flex items-center gap-3 mb-2">
          <DollarSign className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Model Pricing & Ratings</h1>
        </div>
        <p className="text-muted-foreground">
          Pricing information for generation and evaluation models. All prices are per million tokens.
        </p>
      </div>

      {/* FPF Generation Models Section */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <Zap className="h-6 w-6 text-blue-500" />
          <h2 className="text-2xl font-semibold">FPF Generation Models</h2>
          <span className="text-sm text-muted-foreground">({FPF_MODELS.length} models)</span>
        </div>
        <div className="rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="text-left p-4 font-semibold">Provider</th>
                  <th className="text-left p-4 font-semibold">Model</th>
                  <th className="text-right p-4 font-semibold">Input Price</th>
                  <th className="text-right p-4 font-semibold">Output Price</th>
                  <th className="text-right p-4 font-semibold">Avg per 1K</th>
                </tr>
              </thead>
              <tbody>
                {FPF_MODELS.map((model, idx) => (
                  <tr 
                    key={`fpf-${idx}`}
                    className={idx % 2 === 0 ? 'bg-background' : 'bg-muted/20'}
                  >
                    <td className="p-4">
                      <span className="font-medium text-sm">{model.provider}</span>
                    </td>
                    <td className="p-4">
                      <span className="font-mono text-xs">{model.model}</span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm text-green-600 dark:text-green-400 font-medium">
                        {model.input}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1">/1M</span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm text-orange-600 dark:text-orange-400 font-medium">
                        {model.output}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1">/1M</span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-xs font-mono text-muted-foreground">
                        {model.avg1k}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Eval Models Section */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <Scale className="h-6 w-6 text-purple-500" />
          <h2 className="text-2xl font-semibold">Evaluation Judge Models</h2>
          <span className="text-sm text-muted-foreground">({EVAL_MODELS.length} models)</span>
        </div>
        <div className="rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="text-left p-4 font-semibold">Provider</th>
                  <th className="text-left p-4 font-semibold">Model</th>
                  <th className="text-right p-4 font-semibold">Input Price</th>
                  <th className="text-right p-4 font-semibold">Output Price</th>
                  <th className="text-right p-4 font-semibold">Avg per 1K</th>
                </tr>
              </thead>
              <tbody>
                {EVAL_MODELS.map((model, idx) => (
                  <tr 
                    key={`eval-${idx}`}
                    className={idx % 2 === 0 ? 'bg-background' : 'bg-muted/20'}
                  >
                    <td className="p-4">
                      <span className="font-medium text-sm">{model.provider}</span>
                    </td>
                    <td className="p-4">
                      <span className="font-mono text-xs">{model.model}</span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm text-green-600 dark:text-green-400 font-medium">
                        {model.input}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1">/1M</span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-sm text-orange-600 dark:text-orange-400 font-medium">
                        {model.output}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1">/1M</span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-xs font-mono text-muted-foreground">
                        {model.avg1k}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Footer Note */}
      <div className="rounded-lg bg-muted/50 p-4 border">
        <p className="text-sm text-muted-foreground">
          <strong>Note:</strong> All prices shown are per million tokens. The "Avg per 1K" column 
          shows the average cost for 1,000 tokens (useful for quick estimates). FPF models are used 
          for document generation, while eval models are the same models used as judges for evaluation.
        </p>
      </div>
    </div>
  )
}
