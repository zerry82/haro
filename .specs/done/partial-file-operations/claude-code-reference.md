# Claude Code Reference: Partial File Operations

작성일: 2026-05-10

## 조사 범위

로컬 `study` 폴더의 Claude Code 구현을 기준으로 확인했다. 이 문서는 외부 문서가 아니라 실제 코드 관찰 결과를 정리한 것이다.

- `study/docs/tools.md`
- `study/src/tools/FileReadTool/FileReadTool.ts`
- `study/src/tools/FileEditTool/FileEditTool.ts`
- `study/src/tools/FileEditTool/types.ts`
- `study/src/tools/FileEditTool/utils.ts`
- `study/src/tools/FileEditTool/prompt.ts`
- `study/src/tools/FileWriteTool/FileWriteTool.ts`
- `study/src/tools/GrepTool/GrepTool.ts`
- `study/src/utils/readFileInRange.ts`
- `study/src/utils/fileStateCache.ts`
- `study/src/utils/queryHelpers.ts`

## 핵심 결론

Claude Code의 부분 파일 작업은 “줄 번호 범위를 직접 덮어쓰기”가 아니라 다음 조합으로 구성된다.

1. `Read`의 `offset`/`limit`으로 큰 파일의 필요한 줄 범위만 읽는다.
2. `Grep`으로 파일/폴더 안의 관련 위치를 regex 기반으로 찾는다.
3. `Edit`은 `old_string`/`new_string` 정확 치환을 수행한다.
4. `Write`는 전체 파일 생성/덮어쓰기용이며, 기존 파일 수정에는 `Edit`을 우선한다.
5. 쓰기 전에 read state, 파일 수정 시각, 권한, 중복 매치, no-op 여부를 검증한다.

따라서 하로의 partial file operations도 `file_replace_range`를 1순위 도구로 보기보다, Claude Code 스타일의 `file_edit(old_string, new_string, replace_all=false)`를 핵심 쓰기 도구로 설계하는 편이 더 안전하다.

## Read: 필요한 구간만 읽기

`FileReadTool`은 다음 입력을 받는다.

- `file_path`: 절대 경로
- `offset`: 읽기 시작 줄 번호, 선택값
- `limit`: 읽을 줄 수, 선택값
- `pages`: PDF 페이지 범위, 선택값

텍스트 파일은 `readFileInRange`로 읽는다. 내부 구현은 작은 일반 파일은 한 번에 읽고, 큰 파일이나 스트림성 입력은 `createReadStream` 기반으로 필요한 줄만 누적한다. 반환 결과에는 선택된 content뿐 아니라 `lineCount`, `totalLines`, `totalBytes`, `readBytes`, `mtimeMs`가 포함된다.

큰 파일이 제한을 넘으면 “전체 파일 대신 `offset`/`limit`을 사용하거나 검색으로 필요한 내용을 찾으라”는 오류가 난다. 이 메시지가 모델의 작업 전략을 부분 읽기 쪽으로 유도한다.

주의할 점은 read state다. Claude Code는 읽은 파일 내용을 `readFileState`에 저장해 이후 편집의 안전장치로 쓴다. 자동 삽입된 메모리 파일처럼 모델이 실제 디스크 전체를 본 것이 아닌 경우에는 `isPartialView`를 표시하고, `Edit`/`Write`가 이를 근거로 쓰기하지 못하게 한다.

## Grep: 검색으로 위치 좁히기

`GrepTool`은 ripgrep 기반 검색 도구다.

주요 입력:

- `pattern`: 정규식 패턴
- `path`: 파일 또는 폴더 범위
- `glob`: 파일명 glob 필터
- `output_mode`: `content`, `files_with_matches`, `count`
- `-A`, `-B`, `-C`, `context`: 매치 주변 줄
- `-n`: 줄 번호 출력
- `-i`: 대소문자 무시
- `type`: 파일 타입 필터
- `head_limit`: 결과 제한, 기본 250, `0`이면 무제한
- `offset`: 검색 결과 페이지네이션
- `multiline`: multiline regex

기본 출력은 파일 목록이고, 필요한 경우에만 `content` 모드로 실제 매치 줄과 문맥을 가져온다. 즉 큰 파일을 처음부터 전부 읽는 대신 검색으로 후보 위치를 줄이고, 그 주변만 읽는 흐름을 권장한다.

## Edit: 정확 문자열 치환

`FileEditTool`의 입력은 다음과 같다.

```json
{
  "file_path": "absolute path",
  "old_string": "text to replace",
  "new_string": "replacement text",
  "replace_all": false
}
```

핵심 검증 규칙:

- `old_string`과 `new_string`이 같으면 실패한다.
- 기존 파일을 편집하려면 먼저 `Read`가 수행되어 있어야 한다.
- 자동 삽입 등으로 생긴 `isPartialView` 상태만으로는 편집할 수 없다.
- 파일이 읽힌 뒤 사용자가 수정했거나 formatter/linter가 바꿨으면 다시 읽으라고 실패한다.
- `old_string`이 파일에 없으면 실패한다.
- `old_string`이 여러 번 등장하고 `replace_all=false`이면 실패한다.
- 여러 번 등장하는 문자열 하나만 바꾸려면 더 큰 주변 문맥을 포함해 유일하게 만들어야 한다.
- `replace_all=true`는 변수명 변경처럼 모든 발생 지점을 바꿀 때 사용한다.
- `.ipynb`는 별도 Notebook edit 도구를 요구한다.
- Windows UNC 경로는 NTLM credential leak 방지를 위해 파일 시스템 접근을 피하고 권한 체크에 맡긴다.

흥미로운 세부 구현:

- CRLF는 내부 비교용으로 LF 정규화한다.
- curly quote와 straight quote 차이를 보정해 매칭하고, 새 문자열에는 기존 quote 스타일을 보존하려 한다.
- 편집은 patch를 만든 뒤 디스크에 쓰고, LSP/VS Code/diff/telemetry/read state를 갱신한다.
- 결과에는 `structuredPatch`, `originalFile`, `replaceAll`, 선택적 `gitDiff`가 포함된다.

## Write: 전체 생성/덮어쓰기

`FileWriteTool`은 파일 생성 또는 전체 내용 교체용이다. 기존 파일을 덮어쓸 때도 사전 read state와 mtime 검증을 수행한다.

중요한 설계 의도는 `Edit` 프롬프트에 드러난다. Claude Code는 “기존 파일은 항상 편집을 우선하고, 명시적으로 필요할 때만 새 파일을 쓰라”고 지시한다. 하로도 기존 파일 일부 수정은 전체 `file_write`가 아니라 `file_edit` 계열로 유도해야 한다.

## Permission / Safety 모델

파일 도구는 읽기와 쓰기를 분리해서 권한을 검사한다.

- `Read`/`Grep`은 read-only다.
- `Edit`/`Write`는 write permission이 필요하다.
- 입력 경로는 `expandPath`로 정규화해 `~`, 상대 경로, slash 차이로 권한 allowlist를 우회하지 못하게 한다.
- 파일 작업 전 permission check가 선행된다.
- 민감한 secret 저장소/설정 파일 편집에는 별도 검증이 있다.
- read state는 LRU + size limit으로 관리한다.

## 하로 설계에 반영할 결정

### 1. `file_edit`을 핵심 부분 쓰기 도구로 추가한다

`file_replace_range`보다 먼저 구현할 도구는 다음 형태가 적합하다.

```json
{
  "path": "파일 경로",
  "old_string": "교체할 정확한 문자열",
  "new_string": "새 문자열",
  "replace_all": false,
  "expected_sha256": "선택"
}
```

하로는 Claude Code처럼 긴 대화 내 read state를 들고 갈 수 있지만, 현재 백엔드 내장 도구/SSE 구조에서는 checksum 기반 충돌 감지도 함께 두는 편이 좋다. 따라서 `expected_sha256`을 선택값으로 두되, 모델 프롬프트는 `file_stats` 또는 `file_read_range`로 checksum을 확보한 뒤 쓰도록 유도한다.

### 2. `file_replace_range`는 보조 도구로 유지한다

줄 번호 범위 교체는 문서 생성이나 기계적 섹션 교체에는 편할 수 있다. 그러나 사용자가 줄 번호를 직접 지정하지 않는 대부분의 코딩/문서 수정에서는 `old_string` 기반 치환이 더 안전하다.

따라서 v1 우선순위는 다음이 자연스럽다.

1. `file_stats`
2. `file_search_content`
3. `file_read_range`
4. `file_edit`
5. `file_append`
6. `file_replace_range`

### 3. `file_search_content`는 ripgrep식 검색 모델을 참고한다

처음부터 단일 파일만 검색하게 만들면 큰 프로젝트에서 위치 탐색 효과가 약하다. v1은 안전하게 시작하더라도 입력 설계는 `path`가 파일 또는 폴더를 받을 수 있게 열어두는 편이 좋다.

권장 입력:

```json
{
  "path": "파일 또는 폴더",
  "query": "검색어 또는 regex",
  "regex": false,
  "case_sensitive": false,
  "glob": "*.md",
  "output_mode": "content",
  "context_lines": 2,
  "max_results": 50,
  "offset": 0
}
```

### 4. 편집 전후 diff를 도구 결과와 trace에 남긴다

Claude Code는 `structuredPatch`와 diff UI를 중심으로 편집 결과를 보여준다. 하로도 최소한 trace/debug에는 다음을 남겨야 한다.

- 매치 개수
- 교체 전/후 줄 수
- diff preview
- checksum 변경 전/후
- `replace_all` 여부
- 충돌 또는 중복 매치 실패 이유

### 5. 모델 프롬프트는 “읽고, 검색하고, 작게 바꾸라”를 명시해야 한다

도구만 추가하면 모델이 계속 전체 파일 쓰기를 고를 수 있다. 시스템/라우터 프롬프트에는 다음 규칙이 필요하다.

- 기존 파일 일부 수정은 `file_write`보다 `file_edit`을 우선한다.
- 큰 파일은 전체 `file_read` 대신 `file_search_content` 또는 `file_read_range`를 먼저 사용한다.
- 정량 요구사항은 `file_stats`로 변경 전후를 측정한다.
- `old_string`은 유일하게 매칭될 만큼의 최소 문맥을 포함한다.
- 중복 매치 실패 시 더 큰 문맥으로 다시 시도하거나, 모든 발생 지점 변경일 때만 `replace_all=true`를 쓴다.

## 하로 v1 성공 기준 보강

- 긴 파일 전체를 읽지 않고 검색과 범위 읽기로 수정 위치를 찾을 수 있다.
- 기존 파일 일부 수정에서 전체 파일 덮어쓰기를 피할 수 있다.
- `old_string`이 없거나 중복되면 쓰지 않고 실패한다.
- checksum 또는 read state가 맞지 않으면 충돌로 실패한다.
- 편집 결과 diff와 측정값이 trace/debug에 남는다.
- selected tools에 쓰기 도구가 없으면 `file_edit`, `file_append`, `file_replace_range` 모두 blocked 된다.
