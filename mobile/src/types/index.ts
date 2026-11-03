export type PostStatus = 
  | 'draft'
  | 'ready_for_review'
  | 'approved'
  | 'scheduled'
  | 'published'
  | 'partially_published'
  | 'failed';

export type JobStatus = 
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

export type JobStep = 
  | 'extracting'
  | 'researching'
  | 'writing'
  | 'image_generation'
  | 'completed'
  | 'failed';

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
}

export interface PostSummary {
  id: string;
  caption: string | null;
  hashtags: string[];
  status: PostStatus;
  content_version: number;
  media_count: number;
  created_at: string;
  updated_at: string;
}

export interface MediaItem {
  id: string;
  url: string;
  filename: string;
  position: number;
}

export interface TargetItem {
  id: string;
  platform: string;
  status: string;
  display_name: string | null;
}

export interface PostDetail {
  id: string;
  caption: string | null;
  hashtags: string[];
  first_comment: string | null;
  first_comment_enabled: boolean;
  status: PostStatus;
  content_version: number;
  media: MediaItem[];
  targets: TargetItem[];
  created_at: string;
  updated_at: string;
}

export interface GenerationJob {
  id: string;
  source_id?: string;
  post_id?: string;
  status: JobStatus;
  current_step: JobStep;
  progress_pct: number;
  error_message?: string;
}

export type RootStackParamList = {
  Login: undefined;
  MainTabs: undefined;
  PostDetail: { postId: string };
  GenerationProgress: { jobId: string };
};

export type MainTabParamList = {
  Feed: undefined;
  QuickCapture: undefined;
  Workspace: undefined;
};

