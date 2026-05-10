import type { SidePanelTabItem, ToolCatalogItem } from '../components/workspaceSidePanelTypes';

export const SIDE_PANEL_TABS: SidePanelTabItem[] = [
  { id: 'files', label: '폴더' },
  { id: 'skills', label: '스킬' },
  { id: 'tools', label: '툴' },
  { id: 'dataSources', label: '데이터소스' },
];

export const TOOL_CATALOG: ToolCatalogItem[] = [
  { name: 'file_create', signature: 'file_create(path, content)', description: '새 파일 생성' },
  { name: 'file_read', signature: 'file_read(path)', description: '파일 내용 읽기' },
  { name: 'file_write', signature: 'file_write(path, content)', description: '기존 파일 덮어쓰기' },
  { name: 'file_delete', signature: 'file_delete(path)', description: '파일 삭제' },
  { name: 'file_move', signature: 'file_move(source_path, target_path)', description: '파일 또는 폴더 이동' },
  { name: 'dir_list', signature: 'dir_list(path)', description: '디렉토리 내용 조회' },
  { name: 'dir_create', signature: 'dir_create(path)', description: '디렉토리 생성' },
  { name: 'dir_delete', signature: 'dir_delete(path, recursive)', description: '디렉토리 삭제' },
  { name: 'file_search', signature: 'file_search(query, limit)', description: '파일명, 경로, 요약 텍스트 검색' },
  { name: 'file_count', signature: 'file_count(path, item_type, recursive)', description: '파일/폴더 개수 조회' },
  { name: 'code_run', signature: 'code_run(filename, code)', description: '샌드박스 안에서 코드 실행' },
  { name: 'web_preview', signature: 'web_preview()', description: '웹앱 배포모드 활성화 및 URL 반환' },
];
