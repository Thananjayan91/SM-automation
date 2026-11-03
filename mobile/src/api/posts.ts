import { apiClient } from './client';
import { PostSummary, PostDetail, PostStatus } from '../types';

export interface ListPostsResponse {
  total: number;
  page: number;
  posts: PostSummary[];
}

export async function apiListPosts(status?: PostStatus, search?: string) {
  let query = '/api/v1/posts?';
  if (status) query += `status=${status}&`;
  if (search) query += `search=${encodeURIComponent(search)}&`;

  return apiClient.request<ListPostsResponse>(query, {
    method: 'GET',
  });
}

export async function apiGetPost(postId: string) {
  return apiClient.request<PostDetail>(`/api/v1/posts/${postId}`, {
    method: 'GET',
  });
}

export async function apiApprovePost(postId: string, versionNumber?: number) {
  return apiClient.request(`/api/v1/posts/${postId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ version_number: versionNumber }),
  });
}

export async function apiUpdatePost(postId: string, updates: { caption?: string; hashtags?: string[] }) {
  return apiClient.request(`/api/v1/posts/${postId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

