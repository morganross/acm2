import { create } from 'zustand';
import { modelsApi, ModelInfo, PricingInfo } from '../api/models';

interface ModelPricing {
  input: number;  // per million USD
  output: number; // per million USD
}

interface ModelCatalogState {
  models: Record<string, ModelInfo>; // provider:model -> {sections: [...], max_output_tokens: int}
  pricing: Record<string, ModelPricing>; // provider/model or provider:model -> {input, output}
  isLoading: boolean;
  error: string | null;
  sortBy: 'name' | 'price';  // Global sort preference
  
  // Computed lists for convenience
  fpfModels: string[];
  fpfFreeModels: string[];  // OpenRouter free tier models
  gptrModels: string[];
  gptrFreeModels: string[];  // OpenRouter free tier models for GPT-R
  drModels: string[];
  drFreeModels: string[];  // OpenRouter free tier models for DR
  evalModels: string[];
  evalFreeModels: string[];  // OpenRouter free tier models for Eval (uses fpf-free)
  combineModels: string[];
  combineFreeModels: string[];  // OpenRouter free tier models for Combine (uses fpf-free)

  fetchModels: () => Promise<void>;
  getMaxOutputTokens: (modelKey: string) => number | null;
  getPricing: (modelKey: string) => ModelPricing | null;
  formatPricing: (modelKey: string) => string;
  isDrNative: (modelKey: string) => boolean;  // Check if model is DR native (bold purple, no eval/combine)
  setSortBy: (method: 'name' | 'price') => void;
  getSortedModels: (models: string[]) => string[];
}

// Convert ACM2 model format to pricing index format
// ACM2: "google:gemini-2.5-flash" -> Pricing: "google/gemini-2.5-flash"
// ACM2: "openrouter:deepseek/deepseek-r1" -> Pricing: "deepseek/deepseek-r1"
// ACM2: "openrouter:meta-llama/llama-3.1-405b-instruct:free" -> Pricing: "meta-llama/llama-3.1-405b-instruct"
function toPricingKey(modelKey: string): string {
  // First try replacing : with /
  let key = modelKey.replace(':', '/');
  // For openrouter models, strip the openrouter/ prefix
  if (key.startsWith('openrouter/')) {
    key = key.substring('openrouter/'.length);
  }
  // Strip :free suffix (free models are same model, just free tier)
  // After the first replace, :free becomes /free at the end
  if (key.endsWith(':free') || key.endsWith('/free')) {
    key = key.replace(/:free$/, '').replace(/\/free$/, '');
  }
  return key;
}

export const useModelCatalog = create<ModelCatalogState>((set, get) => ({
  models: {},
  pricing: {},
  isLoading: false,
  error: null,
  sortBy: 'name',  // Default to alphabetical sort
  fpfModels: [],
  fpfFreeModels: [],
  gptrModels: [],
  gptrFreeModels: [],
  drModels: [],
  drFreeModels: [],
  evalModels: [],
  evalFreeModels: [],
  combineModels: [],
  combineFreeModels: [],

  fetchModels: async () => {
    set({ isLoading: true, error: null });
    try {
      // Fetch models and pricing in parallel
      const [modelsResponse, pricingData] = await Promise.all([
        modelsApi.getModels(),
        modelsApi.getPricing().catch(() => [] as PricingInfo[]),
      ]);
      
      const models = modelsResponse.models;
      
      // Build pricing lookup map
      const pricing: Record<string, ModelPricing> = {};
      for (const p of pricingData) {
        pricing[p.model] = {
          input: p.input_price_per_million_usd,
          output: p.output_price_per_million_usd,
        };
      }
      
      // Compute derived lists based on sections
      const fpfModels = Object.keys(models).filter(m => models[m].sections.includes('fpf'));
      const fpfFreeModels = Object.keys(models).filter(m => models[m].sections.includes('fpf-free'));
      const gptrModels = Object.keys(models).filter(m => models[m].sections.includes('gpt-r'));
      const gptrFreeModels = Object.keys(models).filter(m => models[m].sections.includes('gpt-r-free'));
      const drModels = Object.keys(models).filter(m => models[m].sections.includes('dr'));
      const drFreeModels = Object.keys(models).filter(m => models[m].sections.includes('dr-free'));
      // eval and combine use fpf list (and fpf-free for free models), but EXCLUDE dr_native models
      const evalModels = Object.keys(models).filter(m => models[m].sections.includes('fpf') && !models[m].dr_native);
      const evalFreeModels = Object.keys(models).filter(m => models[m].sections.includes('fpf-free') && !models[m].dr_native);
      const combineModels = Object.keys(models).filter(m => models[m].sections.includes('fpf') && !models[m].dr_native);
      const combineFreeModels = Object.keys(models).filter(m => models[m].sections.includes('fpf-free') && !models[m].dr_native);

      set({ 
        models,
        pricing,
        fpfModels, 
        fpfFreeModels,
        gptrModels,
        gptrFreeModels,
        drModels,
        drFreeModels,
        evalModels,
        evalFreeModels,
        combineModels,
        combineFreeModels,
        isLoading: false 
      });
    } catch (error) {
      console.error('Failed to fetch models:', error);
      set({ error: 'Failed to load model list', isLoading: false });
    }
  },
  
  getMaxOutputTokens: (modelKey: string): number | null => {
    const model = get().models[modelKey];
    return model?.max_output_tokens ?? null;
  },
  
  getPricing: (modelKey: string): ModelPricing | null => {
    const pricingMap = get().pricing;
    const key = toPricingKey(modelKey);
    return pricingMap[key] ?? null;
  },
  
  formatPricing: (modelKey: string): string => {
    // Free tier models (ending in :free) are always free
    if (modelKey.endsWith(':free')) {
      return 'FREE';
    }
    // DR native models show "DR Native" instead of token pricing
    const model = get().models[modelKey];
    if (model?.dr_native) {
      return 'DR Native';
    }
    const p = get().getPricing(modelKey);
    if (!p) return '';  // No price found, don't display anything
    // Format as "$0.30/$2.50" (input/output per 1M)
    const fmtIn = p.input < 0.01 ? p.input.toFixed(3) : p.input.toFixed(2);
    const fmtOut = p.output < 0.01 ? p.output.toFixed(3) : p.output.toFixed(2);
    return `$${fmtIn}/$${fmtOut}`;
  },
  
  isDrNative: (modelKey: string): boolean => {
    const model = get().models[modelKey];
    return model?.dr_native === true;
  },
  
  setSortBy: (method: 'name' | 'price') => {
    set({ sortBy: method });
  },
  
  getSortedModels: (models: string[]): string[] => {
    const { sortBy, getPricing } = get();
    const sorted = [...models];
    
    if (sortBy === 'name') {
      // Alphabetical sort by model key
      sorted.sort((a, b) => a.localeCompare(b));
    } else if (sortBy === 'price') {
      // Sort by total price (input + output) ascending, models without pricing go to end
      sorted.sort((a, b) => {
        const priceA = getPricing(a);
        const priceB = getPricing(b);
        
        // Handle :free models (treat as $0)
        const isAFree = a.endsWith(':free');
        const isBFree = b.endsWith(':free');
        
        // Calculate total price (input + output)
        const totalA = isAFree ? 0 : 
          (priceA?.input != null && priceA?.output != null) 
            ? priceA.input + priceA.output 
            : Infinity;
        const totalB = isBFree ? 0 : 
          (priceB?.input != null && priceB?.output != null) 
            ? priceB.input + priceB.output 
            : Infinity;
        
        return totalA - totalB;
      });
    }
    
    return sorted;
  },
}));