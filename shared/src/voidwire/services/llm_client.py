"""OpenRouter-compatible LLM client with slot-based configuration."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from voidwire.services.encryption import decrypt_value

logger = logging.getLogger(__name__)


@dataclass
class LLMSlotConfig:
    """Configuration for a single LLM slot."""

    slot: str
    provider_name: str
    api_endpoint: str
    model_id: str
    api_key_encrypted: str
    max_tokens: int | None = None
    temperature: float = 0.7
    extra_params: dict[str, Any] = field(default_factory=dict)

    @property
    def api_key(self) -> str:
        """Decrypt and return the API key."""
        return decrypt_value(self.api_key_encrypted)


class LLMClient:
    """Vendor-agnostic LLM client using OpenRouter-compatible API."""

    def __init__(self, timeout: float = 120.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)
        self._slots: dict[str, LLMSlotConfig] = {}

    def configure_slot(self, config: LLMSlotConfig) -> None:
        """Register a slot configuration."""
        self._slots[config.slot] = config

    def get_slot(self, slot: str) -> LLMSlotConfig:
        """Get configuration for a slot."""
        if slot not in self._slots:
            raise ValueError(f"LLM slot '{slot}' not configured")
        return self._slots[slot]

    @staticmethod
    def _raise_for_status_with_context(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
            return
        except httpx.HTTPStatusError as exc:
            detail = response.text.strip()
            try:
                body = response.json()
                if isinstance(body, dict):
                    if isinstance(body.get("error"), dict):
                        detail = body["error"].get("message") or body["error"].get("code") or detail
                    elif body.get("error"):
                        detail = str(body["error"])
                    elif body.get("message"):
                        detail = str(body["message"])
            except Exception:
                pass
            if len(detail) > 400:
                detail = detail[:400]
            raise RuntimeError(
                f"LLM API request failed ({response.status_code}) at {response.request.url}: {detail}"
            ) from exc

    async def generate(
        self,
        slot: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Generate a completion using the specified slot.

        Returns the assistant message content.
        """
        config = self.get_slot(slot)
        api_key = config.api_key

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": config.model_id,
            "messages": messages,
            "temperature": temperature if temperature is not None else config.temperature,
        }

        tokens = max_tokens or config.max_tokens
        if tokens:
            payload["max_tokens"] = tokens

        if response_format:
            payload["response_format"] = response_format

        # Merge extra params
        payload.update(config.extra_params)

        endpoint = config.api_endpoint.rstrip("/")
        url = f"{endpoint}/chat/completions"

        logger.info("LLM request to %s slot=%s model=%s", url, slot, config.model_id)

        response = await self._client.post(url, json=payload, headers=headers)
        self._raise_for_status_with_context(response)

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        logger.info("LLM response slot=%s tokens=%s", slot, data.get("usage", {}))
        return content

    async def generate_embeddings(
        self,
        slot: str,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings using the specified slot.

        Returns a list of embedding vectors.
        """
        config = self.get_slot(slot)
        api_key = config.api_key

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config.model_id,
            "input": texts,
        }

        endpoint = config.api_endpoint.rstrip("/")
        url = f"{endpoint}/embeddings"

        response = await self._client.post(url, json=payload, headers=headers)
        self._raise_for_status_with_context(response)

        data = response.json()
        return [item["embedding"] for item in data["data"]]

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


def strip_json_fencing(text: str) -> str:
    """Strip markdown JSON fencing if present."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


async def generate_with_validation(
    client: LLMClient,
    slot: str,
    messages: list[dict[str, str]],
    validate_fn: Any,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    repair_retry: bool = True,
) -> dict:
    """Generate LLM output, parse JSON, validate, with one repair retry.

    Args:
        client: LLM client instance
        slot: LLM slot to use
        messages: Chat messages
        validate_fn: Callable that takes parsed dict and raises on invalid
        temperature: Optional temperature override
        max_tokens: Optional max_tokens override

    Returns:
        Validated parsed JSON dict

    Raises:
        json.JSONDecodeError: If JSON parsing fails after retry
        Exception: If validation fails after retry
    """
    response_text = await client.generate(
        slot, messages, temperature=temperature, max_tokens=max_tokens
    )

    text = strip_json_fencing(response_text)

    try:
        data = json.loads(text)
        validate_fn(data)
        return data
    except (json.JSONDecodeError, Exception) as e:
        if not repair_retry:
            raise
        logger.warning("LLM output validation failed, attempting repair: %s", e)

        repair_messages = messages + [
            {"role": "assistant", "content": response_text},
            {
                "role": "user",
                "content": (
                    f"The following output was invalid:\n{text}\n\n"
                    f"Validation errors:\n{e!s}\n\n"
                    "Return ONLY the corrected JSON, with no other text."
                ),
            },
        ]

        response_text_2 = await client.generate(
            slot, repair_messages, temperature=temperature, max_tokens=max_tokens
        )
        text_2 = strip_json_fencing(response_text_2)
        data_2 = json.loads(text_2)
        validate_fn(data_2)
        return data_2


# --- Non-Latin text detection and translation ---

_NON_LATIN_RE = re.compile(
    "[\u4e00-\u9fff"       # CJK Unified Ideographs
    "\u3400-\u4dbf"        # CJK Extension A
    "\u3000-\u303f"        # CJK Symbols and Punctuation
    "\uff00-\uffef"        # Fullwidth Forms
    "\u3040-\u309f"        # Hiragana
    "\u30a0-\u30ff"        # Katakana
    "\uac00-\ud7af]"       # Hangul
)


def has_non_latin(text: str) -> bool:
    """Check if text contains CJK or other non-Latin characters."""
    return bool(_NON_LATIN_RE.search(text))


def _collect_non_latin_lines(content: dict) -> dict[str, list[tuple[int, str]]]:
    """Scan content fields for lines containing non-Latin characters."""
    hits: dict[str, list[tuple[int, str]]] = {}

    def _check(path: str, text: str) -> None:
        for i, line in enumerate(text.split("\n")):
            if line.strip() and has_non_latin(line):
                hits.setdefault(path, []).append((i, line))

    _check("title", str(content.get("title", "")))
    _check("body", str(content.get("body", "")))
    for si, sec in enumerate(content.get("sections") or []):
        _check(f"sections.{si}.heading", str(sec.get("heading", "")))
        _check(f"sections.{si}.body", str(sec.get("body", "")))
    for ti, th in enumerate(content.get("transit_highlights") or []):
        _check(f"transit_highlights.{ti}", str(th))

    return hits


async def fix_non_latin_content(
    content: dict,
    client: LLMClient,
    slot: str,
) -> tuple[dict, dict]:
    """Detect non-Latin text in reading content and translate to English.

    Returns ``(content, fix_meta)`` where *fix_meta* describes what happened:
    ``{"applied": False}`` when no non-Latin text was detected, or a dict with
    ``applied``, ``lines_detected``, ``lines_fixed``, and optionally
    ``fields_touched`` / ``error`` keys.
    """
    hits = _collect_non_latin_lines(content)
    if not hits:
        return content, {"applied": False}

    lines_to_fix: list[str] = []
    for field_lines in hits.values():
        for _, line in field_lines:
            lines_to_fix.append(line)

    numbered = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(lines_to_fix))
    logger.warning(
        "Non-Latin characters detected in %d line(s), requesting translation",
        len(lines_to_fix),
    )

    try:
        raw = await client.generate(
            slot,
            [
                {
                    "role": "system",
                    "content": (
                        "You are a translator. The user will give you numbered lines "
                        "that contain non-English text (likely Chinese or other CJK). "
                        "Translate each line to natural, fluent English. "
                        "Return ONLY a JSON array of strings in the same order, "
                        "one translated string per input line. No extra commentary."
                    ),
                },
                {"role": "user", "content": numbered},
            ],
            max_tokens=1024,
        )
        cleaned = strip_json_fencing(raw)
        translations: list[str] = json.loads(cleaned)
        if not isinstance(translations, list) or len(translations) != len(lines_to_fix):
            logger.warning("Translation response length mismatch, skipping fix")
            return content, {
                "applied": True,
                "lines_detected": len(lines_to_fix),
                "lines_fixed": 0,
                "error": "response length mismatch",
            }
    except Exception as exc:
        logger.warning("Non-Latin translation call failed, leaving content as-is", exc_info=True)
        return content, {
            "applied": True,
            "lines_detected": len(lines_to_fix),
            "lines_fixed": 0,
            "error": str(exc),
        }

    fix_map: dict[str, str] = {}
    for orig, translated in zip(lines_to_fix, translations):
        fix_map[orig] = str(translated)

    content = dict(content)

    def _replace(text: str) -> str:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line in fix_map:
                lines[i] = fix_map[line]
        return "\n".join(lines)

    fields_touched: list[str] = []

    if "title" in hits:
        content["title"] = _replace(str(content.get("title", "")))
        fields_touched.append("title")
    if "body" in hits:
        content["body"] = _replace(str(content.get("body", "")))
        fields_touched.append("body")

    sections = content.get("sections")
    if sections:
        sections = [dict(s) for s in sections]
        for si, sec in enumerate(sections):
            if f"sections.{si}.heading" in hits:
                sec["heading"] = _replace(str(sec.get("heading", "")))
                fields_touched.append(f"sections.{si}.heading")
            if f"sections.{si}.body" in hits:
                sec["body"] = _replace(str(sec.get("body", "")))
                fields_touched.append(f"sections.{si}.body")
        content["sections"] = sections

    highlights = content.get("transit_highlights")
    if highlights:
        highlights = list(highlights)
        for ti in range(len(highlights)):
            if f"transit_highlights.{ti}" in hits:
                full = str(highlights[ti])
                if full in fix_map:
                    highlights[ti] = fix_map[full]
                    fields_touched.append(f"transit_highlights.{ti}")
        content["transit_highlights"] = highlights

    return content, {
        "applied": True,
        "lines_detected": len(lines_to_fix),
        "lines_fixed": len(lines_to_fix),
        "fields_touched": fields_touched,
    }
