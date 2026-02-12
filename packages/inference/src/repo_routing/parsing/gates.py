from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GateFields:
    issue: str | None
    ai_disclosure: str | None
    provenance: str | None

    @property
    def missing_issue(self) -> bool:
        return self.issue is None

    @property
    def missing_ai_disclosure(self) -> bool:
        return self.ai_disclosure is None

    @property
    def missing_provenance(self) -> bool:
        return self.provenance is None


_ISSUE_URL_RE = re.compile(
    r"https?://github\.com/[^/\s]+/[^/\s]+/(?:issues|pull)/\d+\b", re.IGNORECASE
)
_ISSUE_HASH_RE = re.compile(r"(?<!\w)#\d+\b")
_JIRA_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

_AI_KV_RE = re.compile(
    r"(?im)^\s*(?:ai(?:\s+assist(?:ed|ance)?)?|genai|llm)(?:\s+used)?\s*:\s*(?:yes|no|true|false)\b"
)
_PROV_KV_RE = re.compile(
    r"(?im)^\s*(?:provenance|origin|source)\s*:\s*(?:human|ai|mixed|unknown)\b"
)

_CHECKBOX_RE = re.compile(r"(?im)^\s*[-*]\s*\[(?P<state>[ xX])\]\s*(?P<label>.+?)\s*$")


def _first_match(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0).strip()
    return None


def _first_checked_checkbox_line(text: str, label_re: re.Pattern[str]) -> str | None:
    for m in _CHECKBOX_RE.finditer(text):
        state = m.group("state")
        if state.strip().lower() != "x":
            continue
        label = m.group("label")
        if label_re.search(label):
            return m.group(0).strip()
    return None


def parse_gate_fields(pr_body: str | None) -> GateFields:
    """Best-effort offline parsing of policy/gate fields from a PR body.

    This is intentionally permissive: the goal is to measure whether authors
    filled in common PR-template sections, not to enforce a strict schema.
    """

    text = pr_body or ""

    issue = _first_match(text, [_ISSUE_URL_RE, _ISSUE_HASH_RE, _JIRA_RE])

    ai = _first_match(text, [_AI_KV_RE])
    if ai is None:
        ai = _first_checked_checkbox_line(
            text,
            re.compile(
                r"(?i)\b(ai|genai|llm|copilot|chatgpt|claude)\b|\bno\b.*\bai\b",
                re.IGNORECASE,
            ),
        )

    prov = _first_match(text, [_PROV_KV_RE])
    if prov is None:
        prov = _first_checked_checkbox_line(
            text,
            re.compile(
                r"(?i)\b(provenance|origin|source)\b|\b(human|manual|generated|assisted|mixed)\b",
                re.IGNORECASE,
            ),
        )

    return GateFields(issue=issue, ai_disclosure=ai, provenance=prov)
