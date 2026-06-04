# Haro Design Guide

## Direction

Haro is a workspace that non-developers may keep open for long-running business work. The screen should be functional like an IDE, but it should not feel cold, dense, or intimidating like a developer-only tool.

The baseline direction is a bright studio, quiet panels, and a friendly assistant. Users work with files, chat, automation, and skills, but the first impression should feel as comfortable as a messenger or document tool.

## Visual Principles

1. Start from a bright canvas.
   - Keep the central workspace close to white.
   - Empty content areas should not feel broken or anxious.

2. Separate panels with light gray surfaces.
   - Use the `--color-sidebar` family for the left navigation area and right chat area.
   - Do not cover large areas with dark colors.

3. Keep borders thin and shadows minimal.
   - Use 1px borders to define the screen structure.
   - Use cards only where a real group is needed, such as repeated items, input boxes, and modals.

4. Use accent colors sparingly.
   - The primary accent is green.
   - Pink is the friendly secondary accent.
   - Use pink only where attention is useful, such as active tabs, new chat actions, and status badges.

5. Preserve the density of a work tool.
   - Avoid landing-page spacing and oversized hero typography.
   - File trees, tabs, and chat should be compact enough for repeated use while remaining readable.

## Theme Tokens

Global theme tokens live in `src/frontend/src/theme.css`. Components should use the tokens below whenever possible.

```css
--font-sans
--font-mono

--color-bg
--color-surface
--color-sidebar
--color-sidebar-strong
--color-canvas

--color-border
--color-border-soft

--color-text
--color-text-muted
--color-text-subtle

--color-accent
--color-accent-strong
--color-accent-soft

--color-pink
--color-pink-soft

--color-warning
--color-warning-soft
--color-danger
--color-danger-soft
--color-info
--color-info-soft

--radius-sm
--radius-md
--radius-lg
--shadow-card
```

When a new color seems necessary, first check whether an existing token can solve the problem. Direct ad hoc hex values should be rare exceptions.

## Layout

The default Haro screen has three areas.

1. Left: activity icons and file/skill/tool/data-source panels.
2. Center: file preview, editor, code, and CSV workspace.
3. Right: chat sessions and conversation input.

Panel boundaries can be resized by the user. Preserve minimum widths so text does not collapse, and truncate long file names cleanly.

## Component Rules

### Activity Bar

- Use a white background and a thin right border.
- Show active icons with a pink-soft background.
- Icon buttons must always have hover and focus states.

### Side Panel

- Use `--color-sidebar` for the background.
- Section headers should be small and bold.
- Areas that cannot be edited directly, such as Clean Room, should show a locked or read-only badge.

### File Tree

- Do not over-decorate folders and files.
- Selection and focus states should be clearly distinct.
- User workspace badges are useful, but they should not compete with file names.

### Viewer Tabs

- Place tabs close to the file name.
- Use the pink family for active tabs.
- Keep tab labels short: `Preview`, `Editor`, `Source`, `Code`.

### Editor

- Use a bright CodeMirror theme.
- Use the green accent for the Save button.
- When saving is unavailable, show both a disabled button state and supporting text.

### Chat

- The chat panel is a supporting workspace.
- Use subtle gray and pale-blue message bubbles to distinguish roles.
- Keep the input area white, bordered, and clearly focused.

## Empty States

Empty states should be short and help the user understand the next action.

Good examples:

- `Select a file from the left panel`
- `No connected data sources`
- `No files`

Avoid:

- Long feature descriptions
- Product marketing copy
- Technical-language-heavy explanations

## Accessibility

- Maintain contrast between text and backgrounds.
- Icon buttons need a `title` or another accessible name.
- Clickable areas should not be too small.
- Do not communicate state through color alone. Use badges, text, and disabled states together.

## Do Not

- Cover the whole screen with dark navy or black.
- Use large purple or blue gradients as broad backgrounds.
- Nest cards inside cards.
- Expose long feature explanations inside operational screens.
- Use marketing-page hero compositions inside work surfaces.

## Implementation Notes

- Keep global tokens in `src/frontend/src/theme.css`.
- Import the theme CSS from `src/frontend/src/main.ts`.
- Component styles should reference theme tokens.
- For JavaScript-based themes such as CodeMirror, read tokens with `getComputedStyle(document.documentElement)` when needed.
