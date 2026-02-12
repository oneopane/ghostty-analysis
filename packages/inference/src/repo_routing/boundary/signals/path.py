from __future__ import annotations


def normalize_path(path: str) -> str:
    p = path.strip().replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


def boundary_name_for_path(path: str) -> str:
    normalized = normalize_path(path)
    if "/" not in normalized:
        return "__root__"
    top = normalized.split("/", 1)[0].strip()
    return top or "__root__"


def boundary_id_for_name(name: str) -> str:
    return f"dir:{name}"


def path_boundary(path: str) -> tuple[str, str]:
    name = boundary_name_for_path(path)
    return boundary_id_for_name(name), name
