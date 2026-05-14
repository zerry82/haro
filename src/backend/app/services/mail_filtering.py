from __future__ import annotations

from dataclasses import dataclass

FILTER_FIELDS = {"subject", "sender", "recipient"}
FILTER_OPERATORS = {"contains", "equals", "domain_equals"}
FILTER_EFFECTS = {"allow", "deny"}


@dataclass(frozen=True)
class MailFilterEvaluation:
    decision: str
    matched_filter_ids: list[str]


def evaluate_mail_filters(thread: dict, filters: list[dict] | None) -> MailFilterEvaluation:
    active_filters = [rule for rule in filters or [] if rule.get("enabled", True)]
    deny_matches = [rule for rule in active_filters if _effect(rule) == "deny" and _matches_rule(thread, rule)]
    if deny_matches:
        return MailFilterEvaluation("denied", [_rule_id(rule) for rule in deny_matches])

    allow_rules = [rule for rule in active_filters if _effect(rule) == "allow"]
    if not allow_rules:
        return MailFilterEvaluation("allowed", [])

    allow_matches = [rule for rule in allow_rules if _matches_rule(thread, rule)]
    if allow_matches:
        return MailFilterEvaluation("allowed", [_rule_id(rule) for rule in allow_matches])
    return MailFilterEvaluation("denied", [])


def normalize_filter_rules(filters: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for index, rule in enumerate(filters or []):
        field = str(rule.get("field", "")).strip().lower()
        operator = str(rule.get("operator", "")).strip().lower()
        effect = _effect(rule)
        value = str(rule.get("value", "")).strip()
        if field not in FILTER_FIELDS or operator not in FILTER_OPERATORS or effect not in FILTER_EFFECTS or not value:
            continue
        normalized.append({
            "id": _rule_id(rule, fallback=f"filter-{index + 1}"),
            "effect": effect,
            "field": field,
            "operator": operator,
            "value": value,
            "enabled": bool(rule.get("enabled", True)),
        })
    return normalized


def _matches_rule(thread: dict, rule: dict) -> bool:
    field = str(rule.get("field", "")).strip().lower()
    operator = str(rule.get("operator", "")).strip().lower()
    value = str(rule.get("value", "")).strip()
    if field not in FILTER_FIELDS or operator not in FILTER_OPERATORS or not value:
        return False

    values = _thread_values(thread, field)
    if operator == "contains":
        needle = _casefold(value)
        return any(needle in _casefold(candidate) for candidate in values)
    if operator == "equals":
        needle = _casefold(value)
        return any(needle == _casefold(candidate) for candidate in values)
    if operator == "domain_equals":
        domain = _email_domain(value)
        if not domain:
            domain = _casefold(value).lstrip("@")
        return field in {"sender", "recipient"} and any(_email_domain(candidate) == domain for candidate in values)
    return False


def _thread_values(thread: dict, field: str) -> list[str]:
    if field == "subject":
        return [str(thread.get("subject") or "")]
    if field == "sender":
        return [str(thread.get("sender") or "")]
    recipients = thread.get("recipients") or []
    if isinstance(recipients, str):
        return [recipients]
    return [str(value) for value in recipients]


def _email_domain(value: str) -> str:
    folded = _casefold(value).strip()
    if "@" not in folded:
        return folded.lstrip("@")
    return folded.rsplit("@", 1)[1].strip()


def _effect(rule: dict) -> str:
    effect = str(rule.get("effect", "")).strip().lower()
    return effect if effect in FILTER_EFFECTS else "allow"


def _rule_id(rule: dict, fallback: str = "filter") -> str:
    value = str(rule.get("id") or "").strip()
    return value or fallback


def _casefold(value: str) -> str:
    return value.strip().casefold()

