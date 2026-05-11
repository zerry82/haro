# Partial File Operations Spec

작성일: 2026-05-09

## 문제

현재 하로의 파일 도구는 긴 문서나 큰 HTML 파일을 다룰 때 전체 파일 읽기와 전체 파일 쓰기에 치우치기 쉽다. 이 구조에서는 다음 문제가 발생한다.

- 긴 파일 전체를 모델 컨텍스트에 넣어 비용과 오류 가능성이 커진다.
- 일부만 고치면 되는 작업도 전체 파일 덮어쓰기로 처리되어 기존 내용 손상 위험이 커진다.
- 정량 요구사항이 있어도 파일 길이, 줄 수, 글자 수, 예상 발표 시간 등을 먼저 측정하지 않고 작업이 진행될 수 있다.
- 큰 문서를 확장할 때 실제 증가량을 측정하지 않아 "30배", "3시간 분량", "A4 20장" 같은 요구사항을 과장 보고할 수 있다.
- 라우터가 `file_read`만 선택한 intent turn에서 실행 중 `file_write`가 필요해지는 것처럼 도구 선택과 실제 실행 요구가 어긋날 수 있다.
- 파일 일부를 반복적으로 읽고 덧붙이고 검증하는 안전한 루프가 없다.

Claude Code는 긴 파일을 다룰 때 `Read` 도구의 `offset`/`limit`으로 일부만 읽고, `Grep`으로 위치를 좁힌 뒤, `Edit` 도구의 정확한 문자열 치환으로 국소 수정한다. 하로도 이와 같은 부분 파일 작업 능력이 필요하다.

## Claude Code 코드 조사 요약

자세한 조사 내용은 `claude-code-reference.md`에 정리했다. 핵심 결정은 다음과 같다.

- Claude Code의 부분 수정 핵심은 줄 번호 범위 덮어쓰기가 아니라 `old_string`/`new_string` 기반 정확 치환이다.
- `Read(offset, limit)`와 `Grep`은 큰 파일 전체를 읽지 않기 위한 탐색 도구다.
- `Edit`은 사전 read state, 파일 수정 시각, no-op, 문자열 존재 여부, 중복 매치 여부를 검증한 뒤에만 쓴다.
- `replace_all=false`일 때 `old_string`이 여러 번 매칭되면 실패하며, 단일 위치 수정은 충분한 주변 문맥으로 유일하게 만들어야 한다.
- `Write`는 생성/전체 덮어쓰기용이고, 기존 파일 일부 수정은 `Edit`을 우선한다.

## 목표

- 파일 내용을 검색하고 필요한 구간만 읽을 수 있게 한다.
- 파일 전체를 덮어쓰지 않고 append 또는 정확 문자열 치환을 수행할 수 있게 한다.
- 줄 번호 범위 교체는 보조 도구로 제공하되, 일반 수정의 1순위는 `old_string`/`new_string` 기반 편집으로 둔다.
- 정량 요구사항을 처리하기 전에 파일 통계를 먼저 측정할 수 있게 한다.
- 긴 문서 생성/확장 작업을 `측정 -> 계획 -> 일부 쓰기 -> 재측정 -> 보고` 루프에서 처리하게 한다.
- 기존 파일 저장 위치 정책, 권한 정책, selected tools 차단 정책을 유지한다.
- 도구 결과가 모델과 trace/debug 양쪽에서 검증 가능하도록 구조화한다.

## 비목표

- v1에서 IDE 수준의 diff editor를 만들지 않는다.
- v1에서 모든 문서 품질을 자동 평가하지 않는다.
- v1에서 대용량 바이너리 파일의 부분 편집을 지원하지 않는다.
- v1에서 PDF, DOCX, PPTX 같은 복합 포맷 내부 편집을 범용 지원하지 않는다.
- v1에서 기존 `file_read`, `file_write`를 제거하지 않는다.
- v1에서 selected tools 정책을 우회하지 않는다.

## 대상 파일 범위

v1 대상:

- `.txt`
- `.md`
- `.html`
- `.css`
- `.js`
- `.ts`
- `.json`
- `.py`
- 기타 UTF-8 텍스트 파일

v1 제외:

- 이미지, 영상, 압축 파일
- Office 문서 내부 구조 편집
- 인코딩을 확정하기 어려운 바이너리 또는 혼합 파일

## 도구 목록

### file_stats

파일의 기본 통계를 반환한다.

입력:

```json
{
  "path": "파일 경로"
}
```

출력:

```json
{
  "path": "파일 경로",
  "exists": true,
  "bytes": 12345,
  "chars": 10000,
  "chars_no_whitespace": 8500,
  "lines": 320,
  "words": 1800,
  "korean_eojeol_estimate": 1600,
  "estimated_speech_minutes": {
    "slow": 18,
    "normal": 14,
    "fast": 11
  },
  "sha256": "..."
}
```

사용 목적:

- 긴 파일 작업 전 현재 규모 측정
- 정량 요구사항 검증
- 쓰기 전후 변화량 계산
- 파일 변경 충돌 감지용 checksum 확보

### file_search_content

파일 또는 폴더 내부에서 문자열 또는 정규식으로 위치를 검색한다.

입력:

```json
{
  "path": "파일 또는 폴더 경로",
  "query": "검색어",
  "regex": false,
  "case_sensitive": false,
  "glob": "*.md",
  "output_mode": "content",
  "max_results": 20,
  "offset": 0,
  "context_lines": 2
}
```

출력:

```json
{
  "matches": [
    {
      "line": 42,
      "column": 5,
      "preview": "검색어 주변 내용",
      "context": ["앞 줄", "현재 줄", "뒤 줄"]
    }
  ],
  "truncated": false
}
```

사용 목적:

- 수정 위치 찾기
- 긴 파일에서 관련 섹션만 식별
- `file_edit` 전에 유일한 `old_string` 후보 찾기

### file_read_range

지정한 줄 범위만 읽는다.

입력:

```json
{
  "path": "파일 경로",
  "start_line": 1,
  "line_count": 80
}
```

출력:

```json
{
  "path": "파일 경로",
  "start_line": 1,
  "end_line": 80,
  "total_lines": 320,
  "content": "...",
  "sha256": "..."
}
```

규칙:

- `start_line`은 1부터 시작한다.
- 파일 끝을 넘어가면 가능한 범위까지만 반환하고 경고를 포함한다.
- 너무 큰 범위는 도구 정책에 따라 차단하거나 잘라낸다.

### file_append

파일 끝에 내용을 추가한다.

입력:

```json
{
  "path": "파일 경로",
  "content": "추가할 내용",
  "ensure_newline": true,
  "expected_sha256": "선택"
}
```

출력:

```json
{
  "path": "파일 경로",
  "appended_chars": 1200,
  "new_stats": {},
  "sha256": "..."
}
```

규칙:

- 기존 파일이 없으면 기본적으로 실패한다.
- 새 파일 생성은 기존 `file_create` 또는 별도 create 정책을 따른다.
- `expected_sha256`이 제공되고 현재 파일 checksum과 다르면 충돌로 실패한다.

### file_edit

파일 안의 정확한 문자열을 새 문자열로 치환한다. Claude Code의 `Edit` 도구를 하로 v1의 핵심 부분 수정 도구로 반영한다.

입력:

```json
{
  "path": "파일 경로",
  "old_string": "교체할 정확한 문자열",
  "new_string": "새 문자열",
  "replace_all": false,
  "expected_sha256": "선택"
}
```

출력:

```json
{
  "path": "파일 경로",
  "matched_count": 1,
  "replaced_count": 1,
  "old_stats": {},
  "new_stats": {},
  "sha256": "...",
  "diff_preview": "..."
}
```

규칙:

- `old_string`과 `new_string`이 같으면 실패한다.
- `old_string`이 없으면 실패한다.
- `replace_all=false`인데 `old_string`이 여러 번 매칭되면 실패한다.
- 단일 위치만 바꿔야 하면 `old_string`에 주변 문맥을 포함해 유일하게 만들어야 한다.
- 모든 발생 지점을 바꿀 때만 `replace_all=true`를 사용한다.
- `expected_sha256` mismatch는 충돌로 처리한다.
- 교체 전후 diff preview를 trace/debug에 남긴다.

### file_replace_range

지정한 줄 범위를 새 내용으로 교체한다. 이 도구는 문서 섹션 단위 교체 같은 보조 용도로 둔다. 일반적인 기존 파일 일부 수정은 `file_edit`을 우선한다.

입력:

```json
{
  "path": "파일 경로",
  "start_line": 10,
  "end_line": 20,
  "content": "교체할 내용",
  "expected_sha256": "선택"
}
```

출력:

```json
{
  "path": "파일 경로",
  "replaced_start_line": 10,
  "replaced_end_line": 20,
  "old_line_count": 11,
  "new_line_count": 5,
  "new_stats": {},
  "sha256": "..."
}
```

규칙:

- `start_line`과 `end_line`은 1-based inclusive 범위다.
- `start_line > end_line`이면 실패한다.
- 범위가 파일 밖이면 실패한다.
- 교체 전후 diff preview를 trace/debug에 남긴다.
- `expected_sha256` mismatch는 충돌로 처리한다.

## 작업 루프

긴 파일 또는 정량 요구사항이 있는 파일 작업은 다음 루프를 따른다.

1. `file_stats`로 현재 상태를 측정한다.
2. `file_search_content` 또는 `file_read_range`로 필요한 구간만 파악한다.
3. 필요한 작업량을 계산한다.
4. `file_edit`, `file_append`, 또는 보조적으로 `file_replace_range`로 작은 단위의 변경을 수행한다.
5. 다시 `file_stats`로 결과를 측정한다.
6. 성공 기준과 실제 측정값을 비교한다.
7. 부족하면 계획 또는 TODO를 갱신하고 반복한다.
8. 최종 보고에는 변경 전/후 측정값을 포함한다.

## 정량 요구사항 처리

사용자가 다음과 같은 표현을 쓰면 먼저 측정해야 한다.

- "N배 늘려"
- "N분 분량"
- "A4 N장"
- "짧지 않게"
- "훨씬 길게"
- "객관적으로 맞아?"
- "전체 대본"
- "풀 스크립트"

정량 기준 예시:

- 글자 수
- 공백 제외 글자 수
- 단어 수 또는 한국어 어절 추정치
- 줄 수
- 예상 발화 시간
- 섹션별 분량

최종 보고 예시:

```text
변경 전: 2,420자, 예상 발표 12~15분
변경 후: 36,800자, 예상 발표 165~190분
요구사항: 기존 대비 15배 이상 및 180분 근접
판정: 글자 수 기준 15.2배, 발표 시간 기준 충족
```

## 권한과 라우팅

- 각 도구는 기존 파일 저장 위치 정책을 그대로 적용한다.
- `file_edit`, `file_append`, `file_replace_range`는 쓰기 도구로 분류한다.
- 라우터가 읽기 도구만 선택한 turn에서 쓰기 도구가 필요해지면 실행하지 않고 blocked로 전환한다.
- blocked 메시지는 필요한 추가 도구와 이유를 사용자에게 설명해야 한다.
- 도구 실행 결과에는 raw canonical path 노출 정책을 기존 방식과 맞춘다.

## Trace / Debug 이벤트

다음 이벤트를 추가한다.

- `file_stats_collected`
- `file_content_searched`
- `file_range_read`
- `file_edit_requested`
- `file_edit_completed`
- `file_append_requested`
- `file_append_completed`
- `file_replace_range_requested`
- `file_replace_range_completed`
- `file_checksum_mismatch`
- `quantitative_requirement_measured`
- `partial_file_operation_blocked`

## 성공 기준

- 긴 파일 전체를 읽지 않고 필요한 구간만 읽을 수 있다.
- 긴 파일 전체를 덮어쓰지 않고 append 또는 정확 문자열 치환이 가능하다.
- `file_edit`은 `old_string` 없음, no-op, 중복 매치, checksum mismatch를 쓰기 전에 차단한다.
- 정량 요구사항이 있는 작업은 변경 전/후 측정값을 남긴다.
- checksum mismatch가 있으면 덮어쓰지 않고 충돌로 실패한다.
- 쓰기 도구가 선택되지 않은 turn에서는 부분 쓰기도 차단된다.
- 최종 보고는 실제 파일 통계와 요구사항 충족 여부를 함께 말한다.
- 기존 `file_read`, `file_write`, tool-call 파싱, selected tools 차단 테스트가 깨지지 않는다.

## 결정된 사항

- Claude Code 코드 조사 결과를 반영해 `file_edit(old_string, new_string, replace_all=false)`을 v1 핵심 부분 수정 도구로 둔다.
- `file_replace_range`는 제거하지 않고 보조 도구로 둔다.
- `file_search_content`는 단일 파일과 폴더 범위를 모두 받을 수 있는 입력 구조로 설계한다.
- `file_stats`의 발표 시간 추정식은 공백 기준 토큰을 어절로 보고 느림 110, 보통 140, 빠름 170어절/분으로 계산한다.
- 프론트엔드 디버그 UI는 v1에서 변경하지 않고, diff preview는 도구 결과와 debug trace payload에 남긴다.

## 열린 질문

없음.
