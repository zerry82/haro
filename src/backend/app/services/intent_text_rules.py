from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.models.intent_turn import IntentTurn
from app.services.intent_types import RouterDecision


def casual_response(content: str) -> str:
    normalized = normalize(content)
    if "누구" in normalized or "정체" in normalized:
        return "저는 haro입니다. 파일, 채팅 작업공간, 도구를 이용해 반복 업무를 정리하고 실행을 도와주는 AI 에이전트예요."
    if "뭐 할 수" in normalized or "무엇을 할 수" in normalized:
        return "파일 찾기, 폴더 확인, 문서/리포트 초안 작성, 코드 실행, 웹앱 미리보기 같은 일을 도울 수 있어요. 필요한 작업을 말해주면 먼저 범위를 확인하고 진행할게요."
    if "고마" in normalized or "감사" in normalized:
        return "천만에요. 필요하면 바로 이어서 도와드릴게요."
    return "안녕하세요. 필요한 업무나 확인할 파일이 있으면 편하게 말해주세요."


def clarification_question(route: RouterDecision) -> str:
    if route.question:
        return route.question
    if route.missing_info:
        return f"{route.missing_info[0]} 정보가 필요합니다. 어떤 기준으로 진행할까요?"
    return "진행하기 전에 작업 범위를 조금만 더 알려주세요."


def ambiguous_reference_question(candidates: list[IntentTurn]) -> str:
    lines = ["아까 말씀하신 작업이 어떤 건가요?"]
    for index, turn in enumerate(candidates[:3], start=1):
        lines.append(f"{index}. {turn.summary or turn.current_intent or '이전 작업'}")
    return "\n".join(lines)


def parse_json_object(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def normalize(content: str) -> str:
    return " ".join(content.strip().lower().split())


def as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "가능", "실행"}:
            return True
        if normalized in {"false", "no", "n", "0", "불가", "불가능"}:
            return False
    return default


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def is_casual_chat(text: str) -> bool:
    casual_signals = ["안녕", "하이", "hello", "hi", "누구", "뭐 할 수", "무엇을 할 수", "고마", "감사"]
    return any(signal in text for signal in casual_signals) and not looks_like_task(text)


def looks_like_task(text: str) -> bool:
    task_signals = [
        "파일", "폴더", "찾", "검색", "읽", "보여", "만들", "생성", "수정", "삭제",
        "정리", "요약", "자동화", "메일", "리포트", "보고서", "실행", "웹앱", "프리뷰",
        "몇 개", "몇개", "개수", "저장", "업로드",
    ]
    return any(signal in text for signal in task_signals)


def looks_like_new_task(text: str) -> bool:
    return looks_like_task(text)


def looks_like_strong_new_task(text: str) -> bool:
    return looks_like_task(text) and not looks_like_reference(text)


def has_abandon_signal(text: str) -> bool:
    return any(signal in text for signal in ["됐고", "그건 됐", "아니", "새로", "새 프로젝트", "새 작업", "다른"])


def is_cancel(text: str) -> bool:
    return text in {"취소", "그만", "중단", "멈춰"} or "취소해" in text or "그만해" in text


def looks_like_reference(text: str) -> bool:
    return any(signal in text for signal in ["아까", "방금", "그거", "그 파일", "그 리포트", "이전", "전에"])


def looks_like_artifact_reference(text: str) -> bool:
    path_signals = [
        "풀패스", "풀 패스", "full path", "전체 경로", "절대 경로", "경로", "위치",
        "어디 저장", "어디다 저장", "어디에 저장", "어디 있", "어디있", "파일명",
    ]
    if not any(signal in text for signal in path_signals):
        return False
    if any(signal in text for signal in ["말해", "알려", "뭐야", "무엇", "어디", "저장"]):
        return True
    return len(text) <= 30


def reference_candidates(recent: list[IntentTurn]) -> list[IntentTurn]:
    return [
        turn for turn in recent
        if turn.status in {"completed", "failed", "needs_clarification", "waiting_review"}
    ]


def has_count_signal(text: str) -> bool:
    return any(signal in text for signal in ["몇 개", "몇개", "개수", "수가", "몇 명"]) and any(
        target in text for target in ["파일", "폴더", "디렉토리", "루트", "전체"]
    )


def has_search_signal(text: str) -> bool:
    return any(signal in text for signal in ["찾", "검색", "어디 있", "찾아"])


def has_list_signal(text: str) -> bool:
    return any(signal in text for signal in [
        "목록", "뭐 있어", "무엇이 있어", "어떤 파일", "어떤 폴더",
        "파일 있어", "폴더 있어", "보여줘", "나열",
    ])


def has_read_signal(text: str) -> bool:
    return any(signal in text for signal in ["읽어", "열어", "내용", "확인해"])


def has_create_signal(text: str) -> bool:
    return any(signal in text for signal in [
        "만들어", "만들어줘", "생성해", "생성해줘", "작성해", "작성해줘",
        "저장해", "저장해줘", "파일로 만들어", "파일로 저장",
    ])


def has_period_or_target(text: str) -> bool:
    return any(signal in text for signal in ["지난", "이번", "월", "주", "일", ".csv", ".xlsx", ".md", ".html", "/"])


def has_explicit_scope(text: str) -> bool:
    return any(signal in text for signal in ["루트", "전체", "현재", "여기", "채팅", "clean-room", "playground", "/"])


def summarize_text(text: str) -> str:
    return text.strip().replace("\n", " ")[:120]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
