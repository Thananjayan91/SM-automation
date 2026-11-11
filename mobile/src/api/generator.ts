import { apiClient } from './client';
import { GenerationJob } from '../types';

export interface SubmitSourcePayload {
  source_type: 'url' | 'manual';
  source_url?: string;
  headline?: string;
  raw_text?: string;
  notes?: string;
  tone_instruction?: string;
}

export async function apiSubmitSource(payload: SubmitSourcePayload) {
  return apiClient.request<{ id: string; status: string }>('/api/v1/sources', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function apiTriggerGenerate(
  topic?: string,
  sourceId?: string,
  postId?: string,
  language: 'english' | 'tamil' | 'sinhala' = 'english',
  tone?: string
) {
  return apiClient.request<GenerationJob>('/api/v1/posts/generate', {
    method: 'POST',
    body: JSON.stringify({
      topic,
      source_id: sourceId,
      post_id: postId,
      language,
      tone,
    }),
  });
}

export async function apiGetJobStatus(jobId: string) {
  return apiClient.request<GenerationJob>(`/api/v1/jobs/${jobId}`, {
    method: 'GET',
  });
}

export async function apiRetryJob(jobId: string) {
  return apiClient.request<GenerationJob>(`/api/v1/jobs/${jobId}/retry`, {
    method: 'POST',
  });
}

