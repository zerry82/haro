from __future__ import annotations

import json


TOOL_CATALOG: dict[str, dict[str, object]] = {
    "file_create": {
        "purpose": "새 파일 생성",
        "when_to_use": "사용자가 HTML, Markdown, 리포트, 대시보드 등 새 산출물을 만들어 저장하라고 요청할 때",
        "required_args": ["path", "content"],
        "typical_outputs": ["파일 생성 완료 메시지", "linked-files outputs 기록"],
        "description": "file_create(path, content) - 새 파일 생성. 최종 산출물은 `내 폴더/결과/{주제}/{파일명}`처럼 사용자에게 보이는 경로를 명확히 지정해야 합니다.",
    },
    "file_read": {
        "purpose": "파일 내용 읽기",
        "when_to_use": "특정 파일의 실제 내용을 확인하거나, 검색 결과/최근 산출물 파일을 읽어 요약/분석해야 할 때",
        "required_args": ["path"],
        "typical_outputs": ["파일 텍스트 내용"],
        "description": "file_read(path) - 파일 내용 읽기.",
    },
    "file_write": {
        "purpose": "기존 파일 덮어쓰기",
        "when_to_use": "사용자가 기존 파일 수정을 명시했고 전체 내용을 교체해야 할 때",
        "required_args": ["path", "content"],
        "typical_outputs": ["파일 수정 완료 메시지"],
        "description": "file_write(path, content) - 기존 파일 덮어쓰기. 최종 산출물 수정은 `내 폴더/결과/{주제}/{파일명}`처럼 사용자에게 보이는 경로를 명확히 지정해야 합니다.",
    },
    "file_delete": {
        "purpose": "파일 삭제",
        "when_to_use": "사용자가 파일 삭제를 명시적으로 요청할 때",
        "required_args": ["path"],
        "typical_outputs": ["파일 삭제 완료 메시지"],
        "description": "file_delete(path) - 파일 삭제.",
    },
    "file_move": {
        "purpose": "파일 또는 폴더 이동",
        "when_to_use": "사용자가 파일/폴더 이동, 이름 변경, 분류, 통합, 정리를 요청할 때",
        "required_args": ["source_path", "target_path"],
        "typical_outputs": ["이동 완료 메시지", "workspace DB 갱신"],
        "description": "file_move(source_path, target_path) - 파일 또는 폴더 이동/이름 변경. 대상 폴더가 이미 있으면 내부 항목을 병합합니다.",
    },
    "dir_list": {
        "purpose": "디렉토리 직계 목록 조회",
        "when_to_use": "특정 폴더의 하위 파일/폴더 이름 목록을 확인해야 할 때",
        "required_args": ["path"],
        "typical_outputs": ["디렉토리 내 파일/폴더 목록"],
        "description": 'dir_list(path) - SQLite 파일 DB 기반 디렉토리 내용 조회. 기본 path는 "/".',
    },
    "dir_create": {
        "purpose": "디렉토리 생성",
        "when_to_use": "사용자가 새 폴더 생성을 명시적으로 요청할 때",
        "required_args": ["path"],
        "typical_outputs": ["디렉토리 생성 완료 메시지"],
        "description": "dir_create(path) - 디렉토리 생성. 저장 위치가 명확하지 않으면 현재 채팅 working/ 아래에 배치됩니다.",
    },
    "dir_delete": {
        "purpose": "디렉토리 삭제",
        "when_to_use": "사용자가 빈 폴더 또는 정리 후 남은 폴더 삭제를 명시적으로 요청할 때",
        "required_args": ["path"],
        "typical_outputs": ["디렉토리 삭제 완료 메시지", "workspace DB 갱신"],
        "description": "dir_delete(path, recursive) - 디렉토리 삭제. 비어 있지 않은 폴더는 recursive=true가 필요합니다.",
    },
    "code_run": {
        "purpose": "코드 실행",
        "when_to_use": "사용자가 계산/변환/검증을 위해 코드를 실행하라고 요청할 때. 워크스페이스 파일 생성/수정/이동/삭제에는 사용하지 않습니다.",
        "required_args": ["filename", "code"],
        "typical_outputs": ["stdout", "stderr", "exit_code"],
        "description": "code_run(filename, code) - 코드 실행. 별도 지시가 없으면 TypeScript와 .ts 파일명을 사용합니다. 워크스페이스 파일 작업은 전용 파일/폴더 도구를 사용하세요.",
    },
    "web_preview": {
        "purpose": "웹앱 프리뷰 활성화",
        "when_to_use": "사용자가 로컬 웹앱 미리보기 URL을 요청하거나 프리뷰를 켜야 할 때",
        "required_args": [],
        "typical_outputs": ["preview_ready 이벤트", "프리뷰 URL"],
        "description": "web_preview() - 웹앱 배포모드 활성화, 웹 프리뷰 URL 반환.",
    },
    "web_search": {
        "purpose": "외부 웹 검색",
        "when_to_use": "사용자가 웹검색, 최신 정보, 현재 뉴스, 가격, 일정, 규정, 출처 확인 등 외부 웹 정보가 필요한 요청을 할 때",
        "required_args": ["query"],
        "typical_outputs": ["검색 결과 title/url/snippet 목록"],
        "description": "web_search(query, limit, recency_days, domains) - 외부 웹 검색 결과 조회. 검색이 필요하면 설명하지 말고 반드시 이 도구를 호출하세요.",
    },
    "file_export": {
        "purpose": "채팅 산출물 내보내기",
        "when_to_use": "현재 채팅 산출물을 다른 Playground 위치로 복사해야 할 때",
        "required_args": ["source_path", "target_path"],
        "typical_outputs": ["내보낸 대상 경로", "exports 기록"],
        "description": "file_export(source_path, target_path) - 현재 채팅 산출물을 다른 Playground 폴더로 복사하고 연결 관계 기록.",
    },
    "file_search": {
        "purpose": "파일명/경로/요약 텍스트 검색",
        "when_to_use": "의미 있는 파일 찾기, 파일 위치 탐색, 요약 기반 후보 선정이 필요할 때",
        "required_args": ["query"],
        "typical_outputs": ["검색된 파일/폴더 경로와 요약 snippet"],
        "description": "file_search(query, limit, item_type) - SQLite 파일 DB 기반 파일명, 경로, 요약 텍스트 검색.",
    },
    "plan_file_update": {
        "purpose": "Plan Mode 계획 파일 작성",
        "when_to_use": "Plan Mode에서 승인 전 계획 내용을 현재 plan 파일에 기록하거나 갱신해야 할 때",
        "required_args": ["content"],
        "typical_outputs": ["plan_file_updated 이벤트", "계획 파일 수정 완료 메시지"],
        "description": "plan_file_update(content) - Plan Mode의 현재 plan 파일만 생성/교체합니다. path는 받지 않습니다.",
    },
    "plan_approval_request": {
        "purpose": "Plan Mode 승인 요청",
        "when_to_use": "Plan Mode에서 계획이 충분히 수렴되어 사용자 승인 UI를 띄워야 할 때",
        "required_args": ["summary"],
        "typical_outputs": ["plan_approval_requested 이벤트", "승인 대기 상태"],
        "description": "plan_approval_request(summary) - 현재 plan 파일을 사용자에게 승인 요청합니다.",
    },
    "file_count": {
        "purpose": "파일/폴더 개수 조회",
        "when_to_use": "사용자가 파일 수, 폴더 수, 항목 수, 통계, 집계, 개수 기반 대시보드를 요청할 때",
        "required_args": ["path", "item_type", "recursive"],
        "typical_outputs": ["조건에 맞는 파일/폴더 개수"],
        "description": "file_count(path, item_type, recursive) - SQLite 파일 DB 기반 파일/폴더 개수 조회.",
    },
}

TOOL_DETAILS: dict[str, str] = {
    name: str(detail["description"])
    for name, detail in TOOL_CATALOG.items()
}

DEFAULT_TASK_TOOLS = ["file_search", "file_read", "file_create"]


def normalize_tool_names(tool_names: list[str] | str | None) -> list[str]:
    valid, _invalid = validate_tool_names(tool_names)
    return valid


def validate_tool_names(tool_names: list[str] | str | None) -> tuple[list[str], list[str]]:
    if isinstance(tool_names, str):
        tool_names = [tool_names]

    seen: set[str] = set()
    normalized: list[str] = []
    invalid: list[str] = []
    for name in tool_names or []:
        if name in TOOL_DETAILS and name not in seen:
            seen.add(name)
            normalized.append(name)
        elif name not in TOOL_DETAILS:
            invalid.append(str(name))
    return normalized, invalid


def build_tool_catalog() -> str:
    entries = []
    for name, detail in TOOL_CATALOG.items():
        entries.append({
            "name": name,
            "purpose": detail["purpose"],
            "when_to_use": detail["when_to_use"],
            "required_args": detail["required_args"],
            "typical_outputs": detail["typical_outputs"],
        })
    return json.dumps(entries, ensure_ascii=False, indent=2)


def _tool_call_example(tool_name: str) -> str:
    examples = {
        "file_search": '{"tool": "file_search", "args": {"query": "dashboard", "limit": 10, "item_type": "file"}}',
        "file_count": '{"tool": "file_count", "args": {"path": "/", "item_type": "file", "recursive": true}}',
        "dir_list": '{"tool": "dir_list", "args": {"path": "/"}}',
        "file_create": '{"tool": "file_create", "args": {"path": "내 폴더/결과/오늘-기분/mood-forecast.md", "content": "# 제목"}}',
        "file_read": '{"tool": "file_read", "args": {"path": "내 폴더/결과/오늘-기분/report.md"}}',
        "file_write": '{"tool": "file_write", "args": {"path": "내 폴더/결과/오늘-기분/report.md", "content": "# 수정된 내용"}}',
        "file_delete": '{"tool": "file_delete", "args": {"path": "outputs/report.md"}}',
        "file_move": '{"tool": "file_move", "args": {"source_path": "내 폴더/결과/old.md", "target_path": "내 폴더/결과/archive/old.md"}}',
        "dir_create": '{"tool": "dir_create", "args": {"path": "working/new-folder"}}',
        "dir_delete": '{"tool": "dir_delete", "args": {"path": "내 폴더/결과/empty-folder"}}',
        "code_run": '{"tool": "code_run", "args": {"filename": "script.ts", "code": "console.log(1)"}}',
        "web_preview": '{"tool": "web_preview", "args": {}}',
        "web_search": '{"tool": "web_search", "args": {"query": "대한민국 청개구리 개체수 최신 연구", "limit": 5}}',
        "file_export": '{"tool": "file_export", "args": {"source_path": "outputs/report.md", "target_path": "/playground/users/.../report.md"}}',
        "plan_file_update": '{"tool": "plan_file_update", "args": {"content": "# 계획\\n\\n## 목표\\n..."}}',
        "plan_approval_request": '{"tool": "plan_approval_request", "args": {"summary": "계획 초안이 준비되었습니다."}}',
    }
    return examples.get(tool_name, '{"tool": "file_search", "args": {"query": "example"}}')


def build_tool_descriptions(selected_tools: list[str] | None) -> str:
    tools = normalize_tool_names(selected_tools)
    if not tools:
        tools = []
    example_tool = tools[0] if tools else "file_search"

    lines = ["사용 가능한 도구 목록:"]
    if tools:
        for index, name in enumerate(tools, start=1):
            lines.append(f"{index}. {TOOL_DETAILS[name]}")
    else:
        lines.append("- 이번 턴에는 도구를 사용하지 마세요. 일반 텍스트로만 응답하세요.")

    lines.extend([
        "",
        "채팅 작업공간 규칙:",
        "- 사용자가 파일 생성, 작성, 저장, 정리를 명시적으로 요청했지만 위치를 말하지 않았다면 어느 폴더/파일명으로 저장할지 먼저 질문하고 `내 폴더/결과/{적절한 폴더}/{적절한 파일명}` 형태의 추천 경로를 함께 제안하세요.",
        "- 사용자가 \"결과 폴더\", \"결과폴더\", \"내 폴더/결과\"라고 말하면 현재 사용자의 `내 폴더/결과`를 의미합니다.",
        "- 현재 채팅 작업공간의 `outputs`, `working`은 임시/중간 산출물에만 사용하세요.",
        "- 사용자가 파일 생성/저장/수정/삭제를 명시적으로 요청하지 않은 질문에는 파일 변경 도구를 호출하지 말고 텍스트로만 답하세요.",
        "- 명시 경로 없이 파일명만 path에 넣으면 저장 위치 확인이 필요합니다. 도구 호출 전에 사용자에게 확인하세요.",
        "- 최종 산출물 폴더명은 작업 주제 기반으로 정하고, 채팅 날짜, 채팅 제목, chat id를 사용자 결과 폴더명으로 사용하지 마세요.",
        "- 사용자가 `/playground/...`처럼 명시한 합법 경로를 말한 경우에는 그 경로를 사용하세요.",
        "- Clean Room과 `.haro` 내부 메타데이터는 직접 쓰지 마세요.",
        "",
        "파일 DB 조회 규칙:",
        "- 파일/폴더 검색, 개수, 요약 기반 탐색은 이번 턴에 제공된 SQLite 파일 DB 도구만 사용하세요.",
        "- 범위가 명확한 질문에는 해당 범위만 조회하고, 사용자가 요구하지 않은 채팅 폴더나 다른 폴더를 추가 조회하지 마세요.",
        "- 전체 파일 트리는 컨텍스트에 제공되지 않습니다. 파일 목록을 추측하거나 전체를 나열하지 말고 필요한 범위만 도구로 조회하세요.",
    ])
    if "file_export" in tools:
        lines.append("- 채팅 산출물을 다른 폴더로 보내야 하면 `file_export`를 사용하세요.")
    if "file_count" in tools:
        lines.append('- "몇 개"처럼 개수만 묻는 요청에는 `file_count`를 우선 사용하세요.')
    if "file_search" in tools:
        lines.append("- 의미 있는 파일을 찾아야 하면 `file_search`로 파일명, 경로, 요약 텍스트를 검색하세요.")
    if "file_read" in tools:
        lines.append("- 검색 결과의 실제 내용을 확인해야 할 때만 `file_read`를 사용하세요.")
    if "dir_list" in tools:
        lines.append("- 특정 폴더의 직계 목록이 필요할 때만 `dir_list`를 사용하세요.")
    if "file_move" in tools or "dir_delete" in tools:
        lines.extend([
            "- 파일/폴더 이동, 이름 변경, 통합, 정리는 `file_move`와 `dir_delete` 같은 전용 파일 도구로만 수행하세요.",
            "- `code_run`으로 워크스페이스 파일을 직접 생성/수정/이동/삭제하지 마세요. 샌드박스 변경은 사용자 파일 목록과 인덱스에 반영되지 않을 수 있습니다.",
        ])
    if "web_search" in tools:
        lines.extend([
            "- 최신/현재/외부 웹 정보가 필요하면 설명으로 검색했다고 말하지 말고 `web_search`를 호출하세요.",
            "- `web_search` 실행 결과 없이 웹 검색이 불가능하다고 말하지 마세요.",
            "- 웹 검색이 필요한 작업에서 검색이 실패하면 내부 지식으로 대체하지 말고 실패 사실을 명확히 보고하고 멈추세요.",
            "- 웹 검색 결과를 사용한 최종 답변에는 가능한 한 URL 출처를 함께 표시하세요.",
            "- 사용자 파일 전문이나 민감한 workspace 내용을 검색 query로 자동 전송하지 말고 필요한 최소 키워드만 사용하세요.",
        ])
    if "plan_file_update" in tools or "plan_approval_request" in tools:
        lines.extend([
            "- Plan Mode에서는 실제 산출물/코드/프리뷰를 수정하지 말고 plan 파일만 갱신하세요.",
            "- Plan Mode는 요구사항 명확화 -> 근거 수집 -> 계획 승인 순서로 진행하세요.",
            "- plan 파일을 갱신할 때는 `plan_file_update`를 사용하세요. 이 도구는 path를 받지 않습니다.",
            "- plan 파일에는 Requirements, Open Questions, Evidence Ledger, Execution Plan, Acceptance Checks 섹션을 포함하세요.",
            "- Open Questions가 남아 있거나 외부 사실/최신 데이터 기반 리서치/보고서/투자 분석 계획에 기준일과 URL 출처가 없으면 `plan_approval_request`를 호출하지 마세요.",
            "- 계획이 승인받을 만큼 수렴하면 텍스트로 묻지 말고 `plan_approval_request`를 호출하세요.",
        ])

    lines.extend([
        "",
        "도구 호출 출력 계약:",
        "- 도구를 사용할 때는 반드시 아래 fenced block 형식만 사용하세요.",
        "- 사용 가능한 도구 목록에 없는 도구 이름은 절대 호출하지 마세요.",
        "- 필요한 도구가 목록에 없으면 현재 가능한 범위만 텍스트로 설명하고 멈추세요.",
        "- `tool_call`이라는 단어는 반드시 code fence 언어 태그로만 쓰세요.",
        "- code fence 바깥 일반 문장, 제목, 목록, 설명 안에 `tool_call`이라는 단어를 쓰지 마세요.",
        "- 도구 호출 block 뒤에는 어떤 문장도 덧붙이지 말고 즉시 응답을 끝내세요.",
        "- 한 번의 응답에는 정확히 하나의 도구 호출 block만 포함하세요.",
        "- 도구 호출 JSON이 유효하지 않으면 실행되지 않고 교정 요청을 받습니다.",
        "- JSON 문자열 안의 백슬래시는 반드시 유효하게 escape하세요. CSS/HTML content에 불필요한 `\\ ` 조합을 넣지 마세요.",
        "",
        "허용되는 유일한 형식:",
        "```tool_call",
        _tool_call_example(example_tool),
        "```",
        "",
        "금지되는 형식:",
        "- `tool_call` 다음 줄에 JSON을 쓰는 plain text 형식",
        "- 언어 태그가 `json`인 fenced block",
        "- XML/HTML 태그 안의 도구 호출",
        "- bullet/list 안에 JSON을 넣는 형식",
        "- 한 응답에 여러 개의 tool_call block을 넣는 형식",
        "",
        "도구를 사용하지 않고 텍스트만 응답할 때는 일반 텍스트로 응답하세요.",
        "작업 계획을 먼저 설명한 뒤 도구를 호출해야 한다면, 마지막은 반드시 위의 `tool_call` fenced block으로 끝내세요.",
        "한 번에 하나의 도구만 호출하세요.",
        "도구 호출 결과를 받은 후 다음 작업을 진행하세요.",
    ])
    if "code_run" in tools:
        lines.extend([
            "code_run을 사용할 때 별도 지시가 없으면 TypeScript 코드와 `.ts` 파일명을 사용하세요.",
            "code_run은 계산/검증용입니다. 워크스페이스 파일 생성/수정/이동/삭제는 전용 파일/폴더 도구로만 수행하세요.",
        ])
    return "\n".join(lines)
