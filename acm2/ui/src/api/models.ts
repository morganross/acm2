import { apiClient } from './client';

export interface ModelConfigResponse {
  models: Record<string, string[]>;
}

export const modelsApi = {
  getModels: async (): Promise<ModelConfigResponse> => {
    return await apiClient.get<ModelConfigResponse>('/models');
  },
};
