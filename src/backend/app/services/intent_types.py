from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.intent_turn import IntentTurn

ACTIVE_INTENT_STATUSES = {"routing", "needs_clarification", "executing", "waiting_review"}
RECENT_INTENT_LIMIT = 5


@dataclass
class GateDecision:
    decision: str
    reason: str
    intent_turn: IntentTurn | None = None
    candidates: list[IntentTurn] = field(default_factory=list)
    artifact_path: str | None = None
    artifact_kind: str | None = None
    artifact_url: str | None = None
    artifact_action: str | None = None
    confidence: float | None = None
    source: str = "llm"


@dataclass
class ExecutionPolicyDecision:
    profile: str
    confidence: float
    selected_tools: list[str] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    risk_level: str = "low"
    can_execute: bool = True
    question: str | None = None
    reason: str = ""
    source: str = "policy"
    should_enter_plan_mode: bool = False
    plan_mode_reason: str | None = None
    context_confidence: float | None = None
    target_confidence: float | None = None
    source_confidence: float | None = None
    operation_confidence: float | None = None


@dataclass
class RouterDecision:
    intent: str
    confidence: float
    can_execute: bool
    selected_tools: list[str] = field(default_factory=list)
    selected_skills: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)
    risk_level: str = "low"
    question: str | None = None
    reason: str = ""
    source: str = "rule"
    invalid_tools: list[str] = field(default_factory=list)
    routing_context: dict[str, Any] | None = None
    should_enter_plan_mode: bool = False
    plan_mode_reason: str | None = None
    execution_policy: str | None = None
    context_confidence: float | None = None
    target_confidence: float | None = None
    source_confidence: float | None = None
    operation_confidence: float | None = None
