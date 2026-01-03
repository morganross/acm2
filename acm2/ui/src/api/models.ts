import { apiClient } from './client';

export interface ModelInfo {
  sections: string[];
  max_output_tokens: number | null;
}

export interface ModelConfigResponse {
  models: Record<string, ModelInfo>;
}

export const modelsApi = {
  getModels: async (): Promise<ModelConfigResponse> => {
    return await apiClient.get<ModelConfigResponse>('/models');
  },
};
