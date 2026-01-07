import { apiClient } from './client';

export interface ModelInfo {
  sections: string[];
  max_output_tokens: number | null;
}

export interface ModelConfigResponse {
  models: Record<string, ModelInfo>;
}

export interface PricingInfo {
  provider: string;
  model: string;
  input_price_per_million_usd: number;
  output_price_per_million_usd: number;
}

export const modelsApi = {
  getModels: async (): Promise<ModelConfigResponse> => {
    return await apiClient.get<ModelConfigResponse>('/models');
  },
  
  getPricing: async (): Promise<PricingInfo[]> => {
    return await apiClient.get<PricingInfo[]>('/models/pricing');
  },
};
