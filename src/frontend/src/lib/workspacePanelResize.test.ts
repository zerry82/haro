import { describe, expect, it } from 'vitest';

import { computePanelResize } from './workspacePanelResize';

describe('workspacePanelResize', () => {
  it('resizes file panel within workspace constraints', () => {
    expect(computePanelResize({
      panel: 'file',
      deltaX: 1000,
      workspaceWidth: 1200,
      filePanelWidth: 260,
      chatPanelWidth: 400,
      resizeStartFileWidth: 260,
      resizeStartChatWidth: 400,
    })).toEqual({ filePanelWidth: 440, chatPanelWidth: 400 });
  });

  it('resizes chat panel within min and max constraints', () => {
    expect(computePanelResize({
      panel: 'chat',
      deltaX: -1000,
      workspaceWidth: 1800,
      filePanelWidth: 260,
      chatPanelWidth: 400,
      resizeStartFileWidth: 260,
      resizeStartChatWidth: 400,
    })).toEqual({ filePanelWidth: 260, chatPanelWidth: 720 });
  });
});
