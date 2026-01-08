import { DollarSign, Zap, Scale } from 'lucide-react'

// Static FPF Generation Models Data - Complete List (102 token-based models)
const FPF_MODELS = [
  // Google Models
  { provider: 'Google', model: 'google/gemini-2.5-flash-image-preview', input: '$0.30', output: '$2.50', avg1k: '$0.0014' },
  { provider: 'Google', model: 'google/gemini-2.5-flash', input: '$0.30', output: '$2.50', avg1k: '$0.0014' },
  { provider: 'Google', model: 'google/gemini-2.5-flash-lite', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'Google', model: 'google/gemini-2.5-flash-lite-preview-06-17', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'Google', model: 'google/gemini-2.5-pro', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-2.5-pro-preview', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-2.5-pro-preview-05-06', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-3-pro-preview', input: '$2.00', output: '$12.00', avg1k: '$0.0070' },
  { provider: 'Google', model: 'google/gemini-3-flash-preview', input: '$0.50', output: '$3.00', avg1k: '$0.0018' },
  
  // OpenAI GPT-5 Series
  { provider: 'OpenAI', model: 'openai/gpt-5', input: '$0.62', output: '$5.00', avg1k: '$0.0028' },
  { provider: 'OpenAI', model: 'openai/gpt-5-chat', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5-mini', input: '$0.25', output: '$2.00', avg1k: '$0.0011' },
  { provider: 'OpenAI', model: 'openai/gpt-5-nano', input: '$0.05', output: '$0.40', avg1k: '$0.0002' },
  { provider: 'OpenAI', model: 'openai/gpt-5.1', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5.1-chat', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5.2', input: '$1.75', output: '$14.00', avg1k: '$0.0088' },
  { provider: 'OpenAI', model: 'openai/gpt-5.2-chat', input: '$1.75', output: '$14.00', avg1k: '$0.0088' },
  
  // OpenAI GPT-4 Series
  { provider: 'OpenAI', model: 'openai/gpt-4o', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-audio-preview', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-mini', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-mini-search-preview', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-search-preview', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-2024-11-20', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-2024-08-06', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-2024-05-13', input: '$5.00', output: '$15.00', avg1k: '$0.0100' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-mini-2024-07-18', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenAI', model: 'openai/gpt-4o:extended', input: '$6.00', output: '$18.00', avg1k: '$0.0120' },
  { provider: 'OpenAI', model: 'openai/chatgpt-4o-latest', input: '$5.00', output: '$15.00', avg1k: '$0.0100' },
  { provider: 'OpenAI', model: 'openai/gpt-4-turbo', input: '$10.00', output: '$30.00', avg1k: '$0.0200' },
  { provider: 'OpenAI', model: 'openai/gpt-4-turbo-preview', input: '$10.00', output: '$30.00', avg1k: '$0.0200' },
  { provider: 'OpenAI', model: 'openai/gpt-4-1106-preview', input: '$10.00', output: '$30.00', avg1k: '$0.0200' },
  { provider: 'OpenAI', model: 'openai/gpt-4', input: '$30.00', output: '$60.00', avg1k: '$0.0450' },
  { provider: 'OpenAI', model: 'openai/gpt-4-0314', input: '$30.00', output: '$60.00', avg1k: '$0.0450' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-mini', input: '$0.40', output: '$1.60', avg1k: '$0.0010' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-nano', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  
  // OpenAI GPT-3.5 Series
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo', input: '$0.50', output: '$1.50', avg1k: '$0.0010' },
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo-0613', input: '$1.00', output: '$2.00', avg1k: '$0.0015' },
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo-instruct', input: '$1.50', output: '$2.00', avg1k: '$0.0018' },
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo-16k', input: '$3.00', output: '$4.00', avg1k: '$0.0035' },
  
  // OpenAI o-Series (Reasoning)
  { provider: 'OpenAI', model: 'openai/o1', input: '$15.00', output: '$60.00', avg1k: '$0.0375' },
  { provider: 'OpenAI', model: 'openai/o1-pro', input: '$150.00', output: '$600.00', avg1k: '$0.3750' },
  { provider: 'OpenAI', model: 'openai/o1-mini', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o1-mini-2024-09-12', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o3', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/o3-pro', input: '$20.00', output: '$80.00', avg1k: '$0.0500' },
  { provider: 'OpenAI', model: 'openai/o3-mini', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o3-mini-high', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o4-mini', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o4-mini-high', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  
  // OpenAI OSS Series
  { provider: 'OpenAI', model: 'openai/gpt-oss-120b', input: '$0.05', output: '$0.25', avg1k: '$0.0002' },
  { provider: 'OpenAI', model: 'openai/gpt-oss-20b', input: '$0.03', output: '$0.15', avg1k: '$0.0001' },
  { provider: 'OpenAI', model: 'openai/codex-mini', input: '$1.50', output: '$6.00', avg1k: '$0.0038' },
  
  // Anthropic Claude Series
  { provider: 'Anthropic', model: 'anthropic/claude-opus-4-5', input: '$5.00', output: '$25.00', avg1k: '$0.0150' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4-5', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-haiku-4-5', input: '$1.00', output: '$5.00', avg1k: '$0.0030' },
  { provider: 'Anthropic', model: 'anthropic/claude-3.7-sonnet', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-7-sonnet', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-3.5-haiku', input: '$0.80', output: '$4.00', avg1k: '$0.0024' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-5-haiku', input: '$0.80', output: '$4.00', avg1k: '$0.0024' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-opus', input: '$15.00', output: '$75.00', avg1k: '$0.0450' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-sonnet', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-haiku', input: '$0.25', output: '$1.25', avg1k: '$0.0008' },
  
  // DeepSeek
  { provider: 'DeepSeek', model: 'deepseek/deepseek-chat', input: '$0.30', output: '$1.20', avg1k: '$0.0008' },
  { provider: 'DeepSeek', model: 'deepseek/deepseek-r1', input: '$0.70', output: '$2.40', avg1k: '$0.0015' },
  
  // Meta Llama
  { provider: 'Meta', model: 'meta-llama/llama-3.1-405b-instruct', input: '$2.00', output: '$2.00', avg1k: '$0.0020' },
  { provider: 'Meta', model: 'meta-llama/llama-3.1-70b-instruct', input: '$0.40', output: '$0.40', avg1k: '$0.0004' },
  { provider: 'Meta', model: 'meta-llama/llama-3.3-70b-instruct', input: '$0.12', output: '$0.30', avg1k: '$0.0002' },
  
  // Mistral
  { provider: 'Mistral', model: 'mistralai/mistral-large-2411', input: '$2.00', output: '$6.00', avg1k: '$0.0040' },
  { provider: 'Mistral', model: 'mistralai/mistral-small-3.1-24b-instruct', input: '$0.10', output: '$0.30', avg1k: '$0.0002' },
  
  // Perplexity
  { provider: 'Perplexity', model: 'perplexity/sonar-pro', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Perplexity', model: 'perplexity/sonar', input: '$1.00', output: '$1.00', avg1k: '$0.0010' },
  { provider: 'Perplexity', model: 'perplexity/sonar-pro-search', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Perplexity', model: 'perplexity/sonar-reasoning-pro', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  
  // OpenRouter FREE Models
  { provider: 'OpenRouter FREE', model: 'openrouter/meta-llama/llama-3.1-405b-instruct:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nousresearch/hermes-3-llama-3.1-405b:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/meta-llama/llama-3.3-70b-instruct:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/meta-llama/llama-3.2-3b-instruct:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/deepseek/deepseek-r1-0528:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemini-2.0-flash-exp:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemma-3-27b-it:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemma-3n-e2b-it:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemma-3n-e4b-it:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/mistralai/mistral-small-3.1-24b-instruct:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/mistralai/devstral-2512:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/qwen/qwen3-coder:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/xiaomi/mimo-v2-flash:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nvidia/nemotron-nano-12b-v2-vl:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nvidia/nemotron-nano-9b-v2:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/openai/gpt-oss-120b:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/openai/gpt-oss-20b:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/allenai/olmo-3-32b-think:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/allenai/olmo-3.1-32b-think:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/tngtech/deepseek-r1t-chimera:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/tngtech/deepseek-r1t2-chimera:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/tngtech/tng-r1t-chimera:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/arcee-ai/trinity-mini:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/kwaipilot/kat-coder-pro:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nex-agi/deepseek-v3.1-nex-n1:free', input: 'Free', output: 'Free', avg1k: '$0.0000' },
]

// Static Evaluation Judge Models Data - Same as generation models (used as judges for evaluation)
const EVAL_MODELS = [
  // Google Models
  { provider: 'Google', model: 'google/gemini-2.5-flash-image-preview (judge)', input: '$0.30', output: '$2.50', avg1k: '$0.0014' },
  { provider: 'Google', model: 'google/gemini-2.5-flash (judge)', input: '$0.30', output: '$2.50', avg1k: '$0.0014' },
  { provider: 'Google', model: 'google/gemini-2.5-flash-lite (judge)', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'Google', model: 'google/gemini-2.5-flash-lite-preview-06-17 (judge)', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  { provider: 'Google', model: 'google/gemini-2.5-pro (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-2.5-pro-preview (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-2.5-pro-preview-05-06 (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'Google', model: 'google/gemini-3-pro-preview (judge)', input: '$2.00', output: '$12.00', avg1k: '$0.0070' },
  { provider: 'Google', model: 'google/gemini-3-flash-preview (judge)', input: '$0.50', output: '$3.00', avg1k: '$0.0018' },
  
  // OpenAI GPT-5 Series
  { provider: 'OpenAI', model: 'openai/gpt-5 (judge)', input: '$0.62', output: '$5.00', avg1k: '$0.0028' },
  { provider: 'OpenAI', model: 'openai/gpt-5-chat (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5-mini (judge)', input: '$0.25', output: '$2.00', avg1k: '$0.0011' },
  { provider: 'OpenAI', model: 'openai/gpt-5-nano (judge)', input: '$0.05', output: '$0.40', avg1k: '$0.0002' },
  { provider: 'OpenAI', model: 'openai/gpt-5.1 (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5.1-chat (judge)', input: '$1.25', output: '$10.00', avg1k: '$0.0056' },
  { provider: 'OpenAI', model: 'openai/gpt-5.2 (judge)', input: '$1.75', output: '$14.00', avg1k: '$0.0088' },
  { provider: 'OpenAI', model: 'openai/gpt-5.2-chat (judge)', input: '$1.75', output: '$14.00', avg1k: '$0.0088' },
  
  // OpenAI GPT-4 Series
  { provider: 'OpenAI', model: 'openai/gpt-4o (judge)', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-audio-preview (judge)', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-mini (judge)', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-mini-search-preview (judge)', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-search-preview (judge)', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-2024-11-20 (judge)', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-2024-08-06 (judge)', input: '$2.50', output: '$10.00', avg1k: '$0.0063' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-2024-05-13 (judge)', input: '$5.00', output: '$15.00', avg1k: '$0.0100' },
  { provider: 'OpenAI', model: 'openai/gpt-4o-mini-2024-07-18 (judge)', input: '$0.15', output: '$0.60', avg1k: '$0.0004' },
  { provider: 'OpenAI', model: 'openai/gpt-4o:extended (judge)', input: '$6.00', output: '$18.00', avg1k: '$0.0120' },
  { provider: 'OpenAI', model: 'openai/chatgpt-4o-latest (judge)', input: '$5.00', output: '$15.00', avg1k: '$0.0100' },
  { provider: 'OpenAI', model: 'openai/gpt-4-turbo (judge)', input: '$10.00', output: '$30.00', avg1k: '$0.0200' },
  { provider: 'OpenAI', model: 'openai/gpt-4-turbo-preview (judge)', input: '$10.00', output: '$30.00', avg1k: '$0.0200' },
  { provider: 'OpenAI', model: 'openai/gpt-4-1106-preview (judge)', input: '$10.00', output: '$30.00', avg1k: '$0.0200' },
  { provider: 'OpenAI', model: 'openai/gpt-4 (judge)', input: '$30.00', output: '$60.00', avg1k: '$0.0450' },
  { provider: 'OpenAI', model: 'openai/gpt-4-0314 (judge)', input: '$30.00', output: '$60.00', avg1k: '$0.0450' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1 (judge)', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-mini (judge)', input: '$0.40', output: '$1.60', avg1k: '$0.0010' },
  { provider: 'OpenAI', model: 'openai/gpt-4.1-nano (judge)', input: '$0.10', output: '$0.40', avg1k: '$0.0003' },
  
  // OpenAI GPT-3.5 Series
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo (judge)', input: '$0.50', output: '$1.50', avg1k: '$0.0010' },
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo-0613 (judge)', input: '$1.00', output: '$2.00', avg1k: '$0.0015' },
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo-instruct (judge)', input: '$1.50', output: '$2.00', avg1k: '$0.0018' },
  { provider: 'OpenAI', model: 'openai/gpt-3.5-turbo-16k (judge)', input: '$3.00', output: '$4.00', avg1k: '$0.0035' },
  
  // OpenAI o-Series (Reasoning)
  { provider: 'OpenAI', model: 'openai/o1 (judge)', input: '$15.00', output: '$60.00', avg1k: '$0.0375' },
  { provider: 'OpenAI', model: 'openai/o1-pro (judge)', input: '$150.00', output: '$600.00', avg1k: '$0.3750' },
  { provider: 'OpenAI', model: 'openai/o1-mini (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o1-mini-2024-09-12 (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o3 (judge)', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  { provider: 'OpenAI', model: 'openai/o3-pro (judge)', input: '$20.00', output: '$80.00', avg1k: '$0.0500' },
  { provider: 'OpenAI', model: 'openai/o3-mini (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o3-mini-high (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o4-mini (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  { provider: 'OpenAI', model: 'openai/o4-mini-high (judge)', input: '$1.10', output: '$4.40', avg1k: '$0.0027' },
  
  // OpenAI OSS Series
  { provider: 'OpenAI', model: 'openai/gpt-oss-120b (judge)', input: '$0.05', output: '$0.25', avg1k: '$0.0002' },
  { provider: 'OpenAI', model: 'openai/gpt-oss-20b (judge)', input: '$0.03', output: '$0.15', avg1k: '$0.0001' },
  { provider: 'OpenAI', model: 'openai/codex-mini (judge)', input: '$1.50', output: '$6.00', avg1k: '$0.0038' },
  
  // Anthropic Claude Series
  { provider: 'Anthropic', model: 'anthropic/claude-opus-4-5 (judge)', input: '$5.00', output: '$25.00', avg1k: '$0.0150' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4-5 (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-sonnet-4 (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-haiku-4-5 (judge)', input: '$1.00', output: '$5.00', avg1k: '$0.0030' },
  { provider: 'Anthropic', model: 'anthropic/claude-3.7-sonnet (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-7-sonnet (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-3.5-haiku (judge)', input: '$0.80', output: '$4.00', avg1k: '$0.0024' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-5-haiku (judge)', input: '$0.80', output: '$4.00', avg1k: '$0.0024' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-opus (judge)', input: '$15.00', output: '$75.00', avg1k: '$0.0450' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-sonnet (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Anthropic', model: 'anthropic/claude-3-haiku (judge)', input: '$0.25', output: '$1.25', avg1k: '$0.0008' },
  
  // DeepSeek
  { provider: 'DeepSeek', model: 'deepseek/deepseek-chat (judge)', input: '$0.30', output: '$1.20', avg1k: '$0.0008' },
  { provider: 'DeepSeek', model: 'deepseek/deepseek-r1 (judge)', input: '$0.70', output: '$2.40', avg1k: '$0.0015' },
  
  // Meta Llama
  { provider: 'Meta', model: 'meta-llama/llama-3.1-405b-instruct (judge)', input: '$2.00', output: '$2.00', avg1k: '$0.0020' },
  { provider: 'Meta', model: 'meta-llama/llama-3.1-70b-instruct (judge)', input: '$0.40', output: '$0.40', avg1k: '$0.0004' },
  { provider: 'Meta', model: 'meta-llama/llama-3.3-70b-instruct (judge)', input: '$0.12', output: '$0.30', avg1k: '$0.0002' },
  
  // Mistral
  { provider: 'Mistral', model: 'mistralai/mistral-large-2411 (judge)', input: '$2.00', output: '$6.00', avg1k: '$0.0040' },
  { provider: 'Mistral', model: 'mistralai/mistral-small-3.1-24b-instruct (judge)', input: '$0.10', output: '$0.30', avg1k: '$0.0002' },
  
  // Perplexity
  { provider: 'Perplexity', model: 'perplexity/sonar-pro (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Perplexity', model: 'perplexity/sonar (judge)', input: '$1.00', output: '$1.00', avg1k: '$0.0010' },
  { provider: 'Perplexity', model: 'perplexity/sonar-pro-search (judge)', input: '$3.00', output: '$15.00', avg1k: '$0.0090' },
  { provider: 'Perplexity', model: 'perplexity/sonar-reasoning-pro (judge)', input: '$2.00', output: '$8.00', avg1k: '$0.0050' },
  
  // OpenRouter FREE Models
  { provider: 'OpenRouter FREE', model: 'openrouter/meta-llama/llama-3.1-405b-instruct:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nousresearch/hermes-3-llama-3.1-405b:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/meta-llama/llama-3.3-70b-instruct:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/meta-llama/llama-3.2-3b-instruct:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/deepseek/deepseek-r1-0528:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemini-2.0-flash-exp:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemma-3-27b-it:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemma-3n-e2b-it:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/google/gemma-3n-e4b-it:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/mistralai/mistral-small-3.1-24b-instruct:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/mistralai/devstral-2512:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/qwen/qwen3-coder:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/xiaomi/mimo-v2-flash:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nvidia/nemotron-nano-12b-v2-vl:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nvidia/nemotron-nano-9b-v2:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/openai/gpt-oss-120b:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/openai/gpt-oss-20b:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/allenai/olmo-3-32b-think:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/allenai/olmo-3.1-32b-think:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/tngtech/deepseek-r1t-chimera:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/tngtech/deepseek-r1t2-chimera:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/tngtech/tng-r1t-chimera:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/arcee-ai/trinity-mini:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/kwaipilot/kat-coder-pro:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
  { provider: 'OpenRouter FREE', model: 'openrouter/nex-agi/deepseek-v3.1-nex-n1:free (judge)', input: 'Free', output: 'Free', avg1k: '$0.0000' },
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
