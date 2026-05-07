export interface TreeNode {
  name: string;
  type: string;
  path: string;
  size?: number;
  children_count?: number;
  total?: number;
  has_more?: boolean;
  loading?: boolean;
  children?: TreeNode[];
  expanded?: boolean;
  loaded?: boolean;
}

export interface FolderCacheEntry {
  items: TreeNode[];
  total: number;
  offset: number;
  has_more: boolean;
  loaded_at: number;
  dirty: boolean;
  loading: boolean;
}

export interface FileContentResponse {
  path: string;
  content: string;
  size: number;
  language: string;
}

export interface FileMutationResponse {
  path: string;
  type: string;
}

export interface FileUploadResponse {
  path: string;
  uploaded: string[];
}

export interface FileSearchItem {
  path: string;
  name: string;
  item_type: 'file' | 'directory';
  language?: string;
  extension?: string;
  room: string;
  access_policy: string;
  summary_status: string;
  summary_snippet: string;
}

export interface FileSearchResponse {
  query: string;
  status: 'ok' | 'search_unavailable';
  items: FileSearchItem[];
}

export interface FileListResponse {
  path: string;
  items: Array<{
    name: string;
    type: string;
    size?: number;
    children_count?: number;
  }>;
  total?: number;
  has_more?: boolean;
  limit?: number;
  offset?: number;
}

export interface LoadDirectoryOptions {
  append?: boolean;
  force?: boolean;
  limit?: number;
}
