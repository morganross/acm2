import { create } from 'zustand';
import { modelsApi, ModelInfo } from '../api/models';

interface ModelCatalogState {
  models: Record<string, ModelInfo>; // provider:model -> {sections: [...], max_output_tokens: int}
  isLoading: boolean;
  error: string | null;
  
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
}

export const useModelCatalog = create<ModelCatalogState>((set, get) => ({
  models: {},
  isLoading: false,
  error: null,
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
      const response = await modelsApi.getModels();
      const models = response.models;
      
      // Compute derived lists based on sections
      const fpfModels = Object.keys(models).filter(m => models[m].sections.includes('fpf'));
      const fpfFreeModels = Object.keys(models).filter(m => models[m].sections.includes('fpf-free'));
      const gptrModels = Object.keys(models).filter(m => models[m].sections.includes('gpt-r'));
      const gptrFreeModels = Object.keys(models).filter(m => models[m].sections.includes('gpt-r-free'));
      const drModels = Object.keys(models).filter(m => models[m].sections.includes('dr'));
      const drFreeModels = Object.keys(models).filter(m => models[m].sections.includes('dr-free'));
      // eval and combine use fpf list (and fpf-free for free models)
      const evalModels = Object.keys(models).filter(m => models[m].sections.includes('fpf'));
      const evalFreeModels = Object.keys(models).filter(m => models[m].sections.includes('fpf-free'));
      const combineModels = Object.keys(models).filter(m => models[m].sections.includes('fpf'));
      const combineFreeModels = Object.keys(models).filter(m => models[m].sections.includes('fpf-free'));

      set({ 
        models, 
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
}));