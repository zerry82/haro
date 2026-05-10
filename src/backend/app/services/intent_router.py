from __future__ import annotations

from app.services.execution_policy import policy_to_router_decision, resolve_execution_policy
from app.services.intent_resolution import ResolvedIntentContext
from app.services.intent_types import RouterDecision


async def llm_route(resolved: ResolvedIntentContext) -> RouterDecision | None:
    """Semantic LLM routing is disabled in the context-preserving agent loop.

    The executor now receives broad execution policy and working context, then
    decides concrete meaning from the full conversation and tool results.
    """
    return None


def rule_route(resolved: ResolvedIntentContext) -> RouterDecision:
    return policy_to_router_decision(resolve_execution_policy(resolved), resolved)


def fallback_router_decision(resolved: ResolvedIntentContext) -> RouterDecision:
    return rule_route(resolved)
