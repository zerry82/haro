from __future__ import annotations

import json
import re
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Any

DOCUMENT_ATTACHMENT_EXTENSIONS = {"pdf", "txt", "md", "csv", "xlsx", "xls", "ppt", "pptx", "png", "jpeg", "jpg"}
LOW_INFORMATION_BODY_PATTERNS = (
    "첨부",
    "첨부파일",
    "첨부 파일",
    "확인",
    "확인 부탁",
    "확인해주세요",
    "참고",
    "전달",
    "파일 확인",
    "attached",
    "attachment",
    "please find",
)


@dataclass(frozen=True)
class ManagementDecision:
    decision: str
    source: str
    reason: str
    matched_rule_ids: list[str]


class MailManagementPolicyStore:
    def __init__(self, workspace_path: str) -> None:
        self.root = Path(workspace_path).resolve() / ".haro" / "cache" / "mail" / "management-policies"

    def load(self, user_id: str) -> dict[str, Any]:
        path = self._path(user_id)
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty_policy()
        return normalize_management_policy(parsed)

    def save(self, user_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_management_policy(policy)
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(user_id).write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
        return normalized

    def set_manual_override(
        self,
        user_id: str,
        thread_id: str,
        decision: str,
        reason: str = "",
        *,
        source_ref: str = "",
    ) -> dict[str, Any]:
        policy = self.load(user_id)
        overrides = [
            row
            for row in policy["manual_overrides"]
            if row.get("thread_id") != thread_id and (not source_ref or row.get("source_ref") != source_ref)
        ]
        overrides.append({
            "thread_id": thread_id,
            "source_ref": source_ref,
            "decision": decision if decision in {"managed", "excluded"} else "managed",
            "reason": reason or "사용자가 수동으로 관리 상태를 지정함",
        })
        policy["manual_overrides"] = overrides
        return self.save(user_id, policy)

    def _path(self, user_id: str) -> Path:
        return self.root / f"{user_id}.json"


def normalize_management_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = policy if isinstance(policy, dict) else {}
    return {
        "whitelist_rules": _normalize_rules(policy.get("whitelist_rules")),
        "blacklist_rules": _normalize_rules(policy.get("blacklist_rules")),
        "llm_blacklist_rules": _normalize_llm_rules(policy.get("llm_blacklist_rules")),
        "manual_overrides": _normalize_overrides(policy.get("manual_overrides")),
    }


def apply_management_policy(threads: list[dict[str, Any]], policy: dict[str, Any] | None) -> list[dict[str, Any]]:
    normalized = normalize_management_policy(policy)
    return [apply_management_to_thread(thread, normalized) for thread in threads]


def apply_management_to_thread(thread: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_management_policy(policy)
    thread = dict(thread)
    attachments = [enrich_attachment(attachment) for attachment in thread.get("attachments") or []]
    metadata = dict(thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {})
    metadata["attachment_signals"] = attachment_signals(attachments)
    metadata["primary_context_source"] = primary_context_source(
        body_sample=str(metadata.get("body_sample") or thread.get("body") or ""),
        attachments=attachments,
    )
    metadata["mail_core_text"] = build_mail_core_text(thread, attachments, metadata)
    thread["attachments"] = attachments

    decision = decide_management(thread, normalized, metadata)
    metadata["management_decision"] = decision.decision
    metadata["decision_source"] = decision.source
    metadata["decision_reason"] = decision.reason
    metadata["matched_rule_ids"] = decision.matched_rule_ids
    thread["metadata"] = metadata
    if decision.decision == "excluded":
        thread["inclusion_decision"] = "denied"
    elif decision.source == "manual_override":
        thread["inclusion_decision"] = "allowed"
    else:
        thread["inclusion_decision"] = str(thread.get("inclusion_decision") or "allowed")
    return thread


def decide_management(
    thread: dict[str, Any],
    policy: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> ManagementDecision:
    normalized = normalize_management_policy(policy)
    metadata = metadata or {}
    thread_id = str(thread.get("id") or thread.get("thread_id") or thread.get("source_ref") or "")
    for override in normalized["manual_overrides"]:
        if override.get("thread_id") == thread_id or override.get("source_ref") == thread.get("source_ref"):
            decision = "managed" if override.get("decision") == "managed" else "excluded"
            return ManagementDecision(decision, "manual_override", str(override.get("reason") or ""), [])

    whitelist_matches = _matching_rules(thread, normalized["whitelist_rules"], metadata)
    if whitelist_matches:
        return ManagementDecision("managed", "whitelist", "whitelist 규칙과 매칭됨", [_rule_id(rule) for rule in whitelist_matches])

    blacklist_matches = _matching_rules(thread, normalized["blacklist_rules"], metadata)
    if blacklist_matches:
        return ManagementDecision("excluded", "blacklist", "blacklist 규칙과 매칭됨", [_rule_id(rule) for rule in blacklist_matches])

    llm_match = _llm_blacklist_decision(thread, normalized["llm_blacklist_rules"], metadata)
    if llm_match:
        return llm_match

    return ManagementDecision("managed", "default", "관리 제외 규칙에 해당하지 않음", [])


def enrich_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    row = dict(attachment)
    title = str(row.get("title") or row.get("name") or "attachment")
    extension = str(row.get("extension") or Path(title).suffix.lstrip(".")).casefold()
    summary = str(row.get("summary") or row.get("content_summary") or "").strip()
    row["title"] = title
    row["extension"] = extension
    row["summary"] = summary
    row["key_points"] = row.get("key_points") or _key_points(summary)
    if row.get("extract_status"):
        row["extract_status"] = str(row.get("extract_status"))
    elif summary:
        row["extract_status"] = "summarized"
    elif extension in DOCUMENT_ATTACHMENT_EXTENSIONS:
        row["extract_status"] = "supported_pending"
    else:
        row["extract_status"] = "metadata_only"
    return row


def attachment_signals(attachments: list[dict[str, Any]]) -> dict[str, Any]:
    summarized = [attachment for attachment in attachments if str(attachment.get("summary") or "").strip()]
    supported = [attachment for attachment in attachments if attachment.get("extension") in DOCUMENT_ATTACHMENT_EXTENSIONS]
    return {
        "count": len(attachments),
        "summarized_count": len(summarized),
        "supported_count": len(supported),
        "summary_status": "summarized" if summarized else ("supported_pending" if supported else "metadata_only" if attachments else "none"),
        "titles": [str(attachment.get("title") or "") for attachment in attachments],
    }


def primary_context_source(body_sample: str, attachments: list[dict[str, Any]]) -> str:
    has_attachment_summary = any(str(attachment.get("summary") or "").strip() for attachment in attachments)
    body_has_signal = not _is_low_information_body(body_sample)
    if has_attachment_summary and not body_has_signal:
        return "attachment"
    if has_attachment_summary and body_has_signal:
        return "body_attachment"
    return "body"


def build_mail_core_text(thread: dict[str, Any], attachments: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    attachment_text = "\n".join(
        f"- {attachment.get('title')}: {attachment.get('summary')}"
        for attachment in attachments
        if str(attachment.get("summary") or "").strip()
    )
    actions = json.dumps(metadata.get("extracted_actions") or [], ensure_ascii=False, default=str)
    due_dates = json.dumps(metadata.get("extracted_due_dates") or [], ensure_ascii=False, default=str)
    warnings = json.dumps(metadata.get("structure_warnings") or [], ensure_ascii=False, default=str)
    links = ", ".join(str(item) for item in metadata.get("external_links") or [] if str(item).strip())
    lines = [
        f"제목: {thread.get('subject') or ''}",
        f"발신자: {thread.get('sender') or ''}",
        f"카테고리: {thread.get('category') or ''}",
        f"본문 핵심: {thread.get('summary') or metadata.get('body_sample') or ''}",
        f"첨부 핵심:\n{attachment_text}" if attachment_text else "",
        f"요청사항: {actions}" if actions != "[]" else "",
        f"마감: {due_dates}" if due_dates != "[]" else "",
        f"참조 링크: {links}" if links else "",
        f"구조화 경고: {warnings}" if warnings != "[]" else "",
    ]
    return "\n".join(line for line in lines if line and line.split(":", 1)[-1].strip())


def _normalize_rules(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, rule in enumerate(value if isinstance(value, list) else []):
        if not isinstance(rule, dict):
            continue
        field = str(rule.get("field") or "sender").strip().casefold()
        operator = str(rule.get("operator") or "contains").strip().casefold()
        pattern = str(rule.get("pattern") or rule.get("value") or "").strip()
        if field not in {"subject", "sender", "recipient", "domain", "attachment", "body"}:
            continue
        if operator not in {"contains", "equals", "domain_equals", "regex"}:
            continue
        if not pattern:
            continue
        rows.append({
            "id": _rule_id(rule, f"rule-{index + 1}"),
            "field": field,
            "operator": operator,
            "pattern": pattern,
            "enabled": bool(rule.get("enabled", True)),
        })
    return rows


def _normalize_llm_rules(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, rule in enumerate(value if isinstance(value, list) else []):
        if not isinstance(rule, dict):
            continue
        description = str(rule.get("description") or rule.get("pattern") or "").strip()
        if not description:
            continue
        rows.append({"id": _rule_id(rule, f"llm-rule-{index + 1}"), "description": description, "enabled": bool(rule.get("enabled", True))})
    return rows


def _normalize_overrides(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for override in value if isinstance(value, list) else []:
        if not isinstance(override, dict):
            continue
        thread_id = str(override.get("thread_id") or "").strip()
        source_ref = str(override.get("source_ref") or "").strip()
        decision = str(override.get("decision") or "").strip()
        if decision not in {"managed", "excluded"} or (not thread_id and not source_ref):
            continue
        rows.append({"thread_id": thread_id, "source_ref": source_ref, "decision": decision, "reason": str(override.get("reason") or "")})
    return rows


def _matching_rules(thread: dict[str, Any], rules: list[dict[str, Any]], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    return [rule for rule in rules if rule.get("enabled", True) and _matches_rule(thread, rule, metadata)]


def _matches_rule(thread: dict[str, Any], rule: dict[str, Any], metadata: dict[str, Any]) -> bool:
    values = _rule_values(thread, str(rule.get("field") or ""), metadata)
    pattern = str(rule.get("pattern") or "")
    operator = str(rule.get("operator") or "contains")
    if operator == "regex":
        return any(re.search(pattern, value, re.IGNORECASE) for value in values)
    if operator == "equals":
        return any(value.casefold() == pattern.casefold() for value in values)
    if operator == "domain_equals":
        domain = _email_domain(pattern)
        return any(_email_domain(value) == domain for value in values)
    return any(pattern.casefold() in value.casefold() for value in values)


def _rule_values(thread: dict[str, Any], field: str, metadata: dict[str, Any]) -> list[str]:
    if field == "subject":
        return [str(thread.get("subject") or "")]
    if field == "sender":
        return [str(thread.get("sender") or "")]
    if field == "domain":
        return [_email_domain(str(thread.get("sender") or ""))]
    if field == "recipient":
        return [str(item) for item in thread.get("recipients") or []]
    if field == "attachment":
        return [str(title) for title in (metadata.get("attachment_signals") or {}).get("titles") or []]
    if field == "body":
        return [str(thread.get("summary") or ""), str(metadata.get("body_sample") or ""), str(metadata.get("mail_core_text") or "")]
    return []


def _llm_blacklist_decision(
    thread: dict[str, Any],
    rules: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> ManagementDecision | None:
    active_rules = [rule for rule in rules if rule.get("enabled", True)]
    if not active_rules:
        return None
    haystack = " ".join([
        str(thread.get("subject") or ""),
        str(thread.get("sender") or ""),
        str(thread.get("summary") or ""),
        str(metadata.get("mail_core_text") or ""),
    ]).casefold()
    promotional_markers = ("newsletter", "unsubscribe", "프로모션", "광고", "마케팅 수신", "수신거부", "이벤트")
    if any(marker in haystack for marker in promotional_markers):
        return ManagementDecision("excluded", "llm_blacklist", "LLM blacklist 기준상 관리 불필요 메일로 분류됨", [_rule_id(rule) for rule in active_rules])
    return None


def _is_low_information_body(value: str) -> bool:
    cleaned = " ".join(str(value or "").split()).casefold()
    if not cleaned:
        return True
    if len(cleaned) <= 80:
        return True
    compact = re.sub(r"[\s\W_]+", "", cleaned)
    return any(pattern.replace(" ", "").casefold() in compact for pattern in LOW_INFORMATION_BODY_PATTERNS) and len(cleaned) <= 220


def _key_points(summary: str) -> list[str]:
    if not summary:
        return []
    parts = re.split(r"[.;\n•-]+", summary)
    return [part.strip() for part in parts if part.strip()][:5]


def _email_domain(value: str) -> str:
    address = parseaddr(value)[1] or value
    if "@" not in address:
        return address.casefold().lstrip("@").strip()
    return address.rsplit("@", 1)[1].casefold().strip()


def _rule_id(rule: dict[str, Any], fallback: str = "rule") -> str:
    return str(rule.get("id") or fallback)


def _empty_policy() -> dict[str, Any]:
    return {"whitelist_rules": [], "blacklist_rules": [], "llm_blacklist_rules": [], "manual_overrides": []}
