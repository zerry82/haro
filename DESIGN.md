# Haro Design Guide

## Direction

Haro는 비개발자가 오래 켜두고 일하는 업무 공간이다. 화면은 IDE처럼 기능적이어야 하지만, 개발자 도구처럼 차갑거나 복잡해 보이면 안 된다.

기본 방향은 `밝은 작업실`, `조용한 패널`, `친근한 보조자`다. 사용자는 파일, 채팅, 자동화, 스킬을 다루지만 첫인상은 메신저나 문서 도구처럼 편안해야 한다.

## Visual Principles

1. 밝은 캔버스를 기본으로 둔다.
   - 중앙 작업 공간은 흰색에 가깝게 유지한다.
   - 콘텐츠가 없을 때도 빈 화면이 불안하게 보이지 않아야 한다.

2. 패널은 옅은 회색으로 구분한다.
   - 왼쪽 탐색 영역과 오른쪽 채팅 영역은 `--color-sidebar` 계열을 사용한다.
   - 큰 면적에 진한 색을 깔지 않는다.

3. 경계는 얇게, 그림자는 적게 쓴다.
   - 화면 구조는 1px border로 나눈다.
   - 카드는 반복 항목, 입력 박스, 모달처럼 실제로 묶음이 필요한 곳에만 사용한다.

4. 강조색은 적게 쓴다.
   - 기본 액센트는 green, 친근한 보조 강조는 pink다.
   - pink는 활성 탭, 새 채팅, 상태 뱃지처럼 사용자의 시선이 필요한 곳에만 쓴다.

5. 업무 도구의 밀도를 유지한다.
   - 과한 랜딩 페이지식 여백이나 큰 히어로 타이포는 쓰지 않는다.
   - 파일 트리, 탭, 채팅은 반복 사용에 맞게 촘촘하지만 읽기 쉽게 만든다.

## Theme Tokens

전역 테마는 `src/frontend/src/theme.css`에서 관리한다. 컴포넌트는 가능한 한 아래 토큰을 사용한다.

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

새 색상이 필요하면 먼저 기존 토큰으로 해결할 수 있는지 확인한다. 임의의 hex 값을 직접 넣는 것은 예외적인 경우로 제한한다.

## Layout

Haro의 기본 화면은 세 영역이다.

1. 왼쪽: 활동 아이콘과 파일/스킬/툴/데이터소스 패널
2. 가운데: 파일 프리뷰, 에디터, 코드, CSV 작업 공간
3. 오른쪽: 채팅 세션과 대화 입력

패널 경계는 사용자가 드래그해서 조절할 수 있다. 최소 너비를 지켜 텍스트가 무너지지 않게 하고, 긴 파일명은 말줄임 처리한다.

## Component Rules

### Activity Bar

- 흰 배경과 얇은 오른쪽 경계선을 사용한다.
- 활성 아이콘은 pink soft 배경으로 표시한다.
- 아이콘 버튼은 항상 hover와 focus 상태가 있어야 한다.

### Side Panel

- 배경은 `--color-sidebar`를 사용한다.
- 섹션 헤더는 작은 굵은 글씨로 둔다.
- Clean Room처럼 직접 수정할 수 없는 영역은 잠금/읽기 전용 뱃지로 표현한다.

### File Tree

- 폴더와 파일은 과하게 꾸미지 않는다.
- 선택 상태와 포커스 상태는 명확히 구분한다.
- 사용자의 작업 공간은 뱃지로 표시하되, 파일명보다 튀면 안 된다.

### Viewer Tabs

- 탭은 파일명 옆에 붙여 둔다.
- 활성 탭은 pink 계열로 표시한다.
- 탭 이름은 짧게 유지한다: `프리뷰`, `에디터`, `원본`, `코드`.

### Editor

- 에디터는 밝은 CodeMirror 테마를 사용한다.
- 저장 버튼은 green accent를 사용한다.
- 저장 불가 상태는 버튼 비활성화와 설명 문구를 함께 제공한다.

### Chat

- 채팅 패널은 보조 작업 공간이다.
- 메시지 말풍선은 연한 회색/연한 파랑으로 구분한다.
- 입력창은 흰 배경, 얇은 border, 명확한 focus ring을 유지한다.

## Empty States

빈 상태는 사용자가 다음 행동을 알 수 있게 짧게 쓴다.

좋은 예:

- `좌측에서 파일을 선택하세요`
- `연결된 데이터소스 없음`
- `파일 없음`

피해야 할 예:

- 긴 기능 설명
- 제품 홍보 문구
- 기술 용어 중심 안내

## Accessibility

- 텍스트와 배경의 대비를 유지한다.
- 아이콘 버튼에는 `title` 또는 접근 가능한 이름을 둔다.
- 클릭 가능한 영역은 너무 작게 만들지 않는다.
- 색상만으로 상태를 전달하지 않는다. 뱃지, 텍스트, 비활성화 상태를 함께 사용한다.

## Do Not

- 전체 화면을 진한 네이비나 검정 계열로 덮지 않는다.
- 보라/파랑 그라데이션을 넓은 배경으로 사용하지 않는다.
- 카드 안에 카드를 중첩하지 않는다.
- 기능 설명을 화면에 길게 노출하지 않는다.
- 업무 화면에 마케팅 페이지 같은 히어로 구성을 넣지 않는다.

## Implementation Notes

- 전역 토큰은 `src/frontend/src/theme.css`에 둔다.
- 앱 진입점 `src/frontend/src/main.ts`에서 theme CSS를 import한다.
- 컴포넌트별 스타일은 토큰을 참조한다.
- CodeMirror처럼 JS 기반 테마가 필요한 경우에도 `getComputedStyle(document.documentElement)`로 토큰을 읽어 사용한다.
