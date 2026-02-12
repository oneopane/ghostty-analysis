from __future__ import annotations

from dataclasses import dataclass

from ...router.baselines.mentions import extract_targets


@dataclass(frozen=True)
class ParsedCodeownersOwner:
    kind: str
    name: str
    canonical_id: str


@dataclass(frozen=True)
class ParsedCodeownersRule:
    pattern: str
    owners: list[ParsedCodeownersOwner]
    line: int


def parse_codeowners_rules(text: str) -> list[ParsedCodeownersRule]:
    out: list[ParsedCodeownersRule] = []
    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        pattern = parts[0]
        owner_text = " ".join(parts[1:])
        targets = extract_targets(owner_text)
        if not targets:
            continue

        owners: list[ParsedCodeownersOwner] = []
        for t in targets:
            kind = "team" if t.type.value == "team" else "person"
            owners.append(
                ParsedCodeownersOwner(
                    kind=kind,
                    name=t.name,
                    canonical_id=f"{kind}:{t.name.lower()}",
                )
            )
        out.append(ParsedCodeownersRule(pattern=pattern, owners=owners, line=idx))
    return out


def area_for_pattern(pattern: str) -> str:
    p = pattern.strip().lstrip("/")
    if not p:
        return "__unknown__"
    if p.startswith("*.") or p.startswith("**."):
        return "__root__"
    first = p.split("/", 1)[0]
    if "*" in first or "?" in first or "[" in first:
        return "__root__"
    return first or "__unknown__"
