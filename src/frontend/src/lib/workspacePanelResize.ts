import { clamp } from './workspaceUtils';

export type ResizePanel = 'file' | 'chat';

export const FILE_PANEL_MIN = 220;
export const FILE_PANEL_MAX = 560;
export const CHAT_PANEL_MIN = 300;
export const CHAT_PANEL_MAX = 720;
export const VIEWER_PANEL_MIN = 360;

export function computePanelResize({
  panel,
  deltaX,
  workspaceWidth,
  filePanelWidth,
  chatPanelWidth,
  resizeStartFileWidth,
  resizeStartChatWidth,
}: {
  panel: ResizePanel;
  deltaX: number;
  workspaceWidth: number;
  filePanelWidth: number;
  chatPanelWidth: number;
  resizeStartFileWidth: number;
  resizeStartChatWidth: number;
}) {
  if (panel === 'file') {
    const maxWidth = Math.min(FILE_PANEL_MAX, workspaceWidth - chatPanelWidth - VIEWER_PANEL_MIN);
    return {
      filePanelWidth: clamp(resizeStartFileWidth + deltaX, FILE_PANEL_MIN, Math.max(FILE_PANEL_MIN, maxWidth)),
      chatPanelWidth,
    };
  }

  const maxWidth = Math.min(CHAT_PANEL_MAX, workspaceWidth - filePanelWidth - VIEWER_PANEL_MIN);
  return {
    filePanelWidth,
    chatPanelWidth: clamp(resizeStartChatWidth - deltaX, CHAT_PANEL_MIN, Math.max(CHAT_PANEL_MIN, maxWidth)),
  };
}
