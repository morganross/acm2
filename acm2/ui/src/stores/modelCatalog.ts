import { create } from 'zustand';
import { modelsApi } from '../api/models';

interface ModelCatalogState {
  models: Record<string, string[]>; // provider:model -> [sections]
  isLoading: boolean;
  error: string | null;
  
  // Computed lists for convenience
  fpfModels: string[];
  gptrModels: string[];
  gptrDrModels: string[];
  evalModels: string[];
  combineModels: string[];

  fetchModels: () => Promise<void>;
}

export const useModelCatalog = create<ModelCatalogState>((set) => ({
  models: {},
  isLoading: false,
  error: null,
  fpfModels: [],
  gptrModels: [],
  gptrDrModels: [],
  evalModels: [],
  combineModels: [],

  fetchModels: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await modelsApi.getModels();
      const models = response.models;
      
      // Compute derived lists
      const fpfModels = Object.keys(models).filter(m => models[m].includes('fpf'));
      const gptrModels = Object.keys(models).filter(m => models[m].includes('gpt-r'));
      // gpt-r-DR uses gpt-r list
      const gptrDrModels = Object.keys(models).filter(m => models[m].includes('gpt-r'));
      // eval and combine use fpf list
      const evalModels = Object.keys(models).filter(m => models[m].includes('fpf'));
      const combineModels = Object.keys(models).filter(m => models[m].includes('fpf'));

      set({ 
        models, 
        fpfModels, 
        gptrModels, 
        gptrDrModels, 
        evalModels, 
        combineModels,
        isLoading: false 
      });
    } catch (error) {
      console.error('Failed to fetch models:', error);
      set({ error: 'Failed to load model list', isLoading: false });
    }
  }
}));