from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


SYSTEM_PROMPT_MACRO_ID = "system_prompt.full"
CACHED_SYSTEM_PROMPT_MACRO_ID = "system_prompt.cached_system"
RUNTIME_CONTEXT_PROMPT_MACRO_ID = "system_prompt.runtime_context"
RUNTIME_CONTEXT_HEADER = (
    "[Runtime Context - obey for this turn]\n"
    "이 메시지는 현재 turn에만 적용되는 도구, 라우팅, 작업공간 맥락입니다. "
    "cached system prompt의 공통 규칙보다 구체적인 현재 실행 맥락으로 따르세요."
)


def prompt_macro_ref(macro_id: str = SYSTEM_PROMPT_MACRO_ID) -> dict[str, str]:
    return {"$macro": macro_id}


def prompt_sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def generation_config_debug_payload(generation_config: Any) -> dict[str, Any]:
    if isinstance(generation_config, dict):
        return dict(generation_config)
    if hasattr(generation_config, "model_dump"):
        return generation_config.model_dump(exclude_none=True)
    if hasattr(generation_config, "to_dict"):
        payload = generation_config.to_dict()
        return payload if isinstance(payload, dict) else {"value": payload}
    return {"value": str(generation_config)}


@dataclass(frozen=True)
class PromptSection:
    id: str
    kind: str
    text: str
    cache_scope: str = "runtime"

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def sha256(self) -> str:
        return prompt_sha256(self.text)

    def debug_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "cache_scope": self.cache_scope,
            "sha256": self.sha256,
            "chars": self.chars,
        }


@dataclass(frozen=True)
class PromptBundle:
    sections: tuple[PromptSection, ...]
    separator: str = "\n"

    @classmethod
    def from_sections(cls, sections: list[PromptSection] | tuple[PromptSection, ...]) -> "PromptBundle":
        return cls(tuple(section for section in sections if section.text))

    @property
    def text(self) -> str:
        parts = [self.cached_system_text]
        if self.runtime_context_text:
            parts.append(self.runtime_context_content_text)
        return self.separator.join(part for part in parts if part)

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def sha256(self) -> str:
        return prompt_sha256(self.text)

    @property
    def static_prefix_text(self) -> str:
        return self.cached_system_text

    @property
    def static_prefix_chars(self) -> int:
        return len(self.static_prefix_text)

    @property
    def static_prefix_sha256(self) -> str:
        return prompt_sha256(self.static_prefix_text)

    @property
    def cached_system_sections(self) -> tuple[PromptSection, ...]:
        return tuple(section for section in self.sections if section.cache_scope in {"static", "project", "stable"})

    @property
    def runtime_sections(self) -> tuple[PromptSection, ...]:
        return tuple(section for section in self.sections if section.cache_scope not in {"static", "project", "stable"})

    @property
    def cached_system_text(self) -> str:
        return self.separator.join(section.text for section in self.cached_system_sections)

    @property
    def cached_system_chars(self) -> int:
        return len(self.cached_system_text)

    @property
    def cached_system_sha256(self) -> str:
        return prompt_sha256(self.cached_system_text)

    @property
    def runtime_context_text(self) -> str:
        return self.separator.join(section.text for section in self.runtime_sections)

    @property
    def runtime_context_content_text(self) -> str:
        if not self.runtime_context_text:
            return ""
        return RUNTIME_CONTEXT_HEADER + "\n\n" + self.runtime_context_text

    @property
    def runtime_context_chars(self) -> int:
        return len(self.runtime_context_content_text)

    @property
    def runtime_context_sha256(self) -> str:
        return prompt_sha256(self.runtime_context_content_text)

    def section_summaries(self) -> list[dict[str, Any]]:
        return [section.debug_summary() for section in self.sections]

    def prompt_macros(self) -> dict[str, Any]:
        macros: dict[str, Any] = {
            SYSTEM_PROMPT_MACRO_ID: {
                "id": SYSTEM_PROMPT_MACRO_ID,
                "sha256": self.sha256,
                "chars": self.chars,
                "text": self.text,
                "sections": self.section_summaries(),
            }
        }
        if self.cached_system_text:
            macros[CACHED_SYSTEM_PROMPT_MACRO_ID] = {
                "id": CACHED_SYSTEM_PROMPT_MACRO_ID,
                "sha256": self.cached_system_sha256,
                "chars": self.cached_system_chars,
                "text": self.cached_system_text,
                "sections": [section.debug_summary() for section in self.cached_system_sections],
            }
        if self.runtime_context_content_text:
            macros[RUNTIME_CONTEXT_PROMPT_MACRO_ID] = {
                "id": RUNTIME_CONTEXT_PROMPT_MACRO_ID,
                "sha256": self.runtime_context_sha256,
                "chars": self.runtime_context_chars,
                "text": self.runtime_context_content_text,
                "sections": [section.debug_summary() for section in self.runtime_sections],
            }
        return macros

    def macro_debug_event_payload(self, prompt_cache: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "prompt_macros": self.prompt_macros(),
            "prompt_cache": prompt_cache or self.cache_debug_summary(),
        }

    def cache_debug_summary(self, prompt_cache: dict[str, Any] | None = None) -> dict[str, Any]:
        if prompt_cache:
            return prompt_cache
        return {
            "strategy": "gemini_explicit_stable_system",
            "cache_state": "not_prepared",
            "cached_system_sha256": self.cached_system_sha256,
            "cached_system_chars": self.cached_system_chars,
            "runtime_context_sha256": self.runtime_context_sha256,
            "runtime_context_chars": self.runtime_context_chars,
            "full_sha256": self.sha256,
            "full_chars": self.chars,
        }

    def runtime_context_content(self) -> dict[str, Any] | None:
        if not self.runtime_context_content_text:
            return None
        return {
            "role": "user",
            "parts": [{"text": self.runtime_context_content_text}],
        }

    def model_contents(self, contents: list[dict], *, include_runtime_context: bool) -> list[dict]:
        runtime_context = self.runtime_context_content() if include_runtime_context else None
        return [runtime_context, *contents] if runtime_context else list(contents)

    def _debug_contents(self, contents: list[dict]) -> list[dict]:
        runtime_text = self.runtime_context_content_text
        debug_contents: list[dict] = []
        for entry in contents:
            parts = []
            for part in entry.get("parts", []):
                if runtime_text and part.get("text") == runtime_text:
                    parts.append({"text": prompt_macro_ref(RUNTIME_CONTEXT_PROMPT_MACRO_ID)})
                else:
                    parts.append(dict(part))
            debug_contents.append({**entry, "parts": parts})
        return debug_contents

    def request_debug_payload(
        self,
        *,
        model_name: str,
        contents: list[dict],
        generation_config: dict[str, Any],
        prompt_cache: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        debug_config = generation_config_debug_payload(generation_config)
        if "system_instruction" in debug_config:
            debug_config["system_instruction"] = prompt_macro_ref()
        return {
            "model": model_name,
            "system_instruction": prompt_macro_ref(),
            "contents": self._debug_contents(contents),
            "config": debug_config,
            "system_prompt_hash": self.sha256,
            "system_prompt_chars": self.chars,
            "cached_system_hash": self.cached_system_sha256,
            "cached_system_chars": self.cached_system_chars,
            "runtime_context_hash": self.runtime_context_sha256,
            "runtime_context_chars": self.runtime_context_chars,
            "system_prompt_sections": self.section_summaries(),
            "prompt_cache": self.cache_debug_summary(prompt_cache),
        }
