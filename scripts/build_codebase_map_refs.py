from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs" / "_artifacts"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _schema_table_ref(name: str) -> str:
    raw = name.strip()
    if raw.startswith("examples_index."):
        suffix = raw.split(".", 1)[1]
        return f"codebase_map_pack/schemas/#table-examples_index-{suffix}"
    return f"codebase_map_pack/schemas/#table-{raw}"


def main() -> int:
    ref_map_path = ARTIFACTS / "ref_map.json"
    refs_doc = _read_json(ref_map_path) if ref_map_path.exists() else {}
    refs = refs_doc.get("refs") if isinstance(refs_doc, dict) else {}
    if not isinstance(refs, dict):
        refs = {}

    # module_graph.json
    mg_path = ARTIFACTS / "module_graph.json"
    mg = _read_json(mg_path)
    for n in mg.get("nodes", []):
        if not isinstance(n, dict):
            continue
        name = str(n.get("name") or "")
        if not name:
            continue
        n.setdefault("ref", refs.get(name) or "codebase_map_pack/architecture/")
    _write_json(mg_path, mg)

    # data_lineage_graph.json
    dl_path = ARTIFACTS / "data_lineage_graph.json"
    dl = _read_json(dl_path)
    for d in dl.get("datasets", []):
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "")
        if not name:
            continue
        d.setdefault(
            "ref",
            refs.get(name) or "codebase_map_pack/data_lineage/#dataset-catalog",
        )
    _write_json(dl_path, dl)

    # pipeline_dags.json
    pd_path = ARTIFACTS / "pipeline_dags.json"
    pd = _read_json(pd_path)
    pipeline_anchor = {
        "ingestion": "codebase_map_pack/pipelines/#pipeline-ingestion",
        "inference_artifacts": "codebase_map_pack/pipelines/#pipeline-inference",
        "evaluation": "codebase_map_pack/pipelines/#pipeline-evaluation",
        "experimentation_unified": "codebase_map_pack/pipelines/#pipeline-experimentation",
        "export_parquet": "codebase_map_pack/pipelines/#pipeline-export",
    }
    for p in pd.get("pipelines", []):
        if not isinstance(p, dict):
            continue
        pname = str(p.get("name") or "")
        pref = pipeline_anchor.get(pname, "codebase_map_pack/pipelines/#pipelines")
        p.setdefault("ref", pref)
        for node in p.get("nodes", []):
            if isinstance(node, dict):
                node.setdefault("ref", pref)
    _write_json(pd_path, pd)

    # schema_catalog.json
    sc_path = ARTIFACTS / "schema_catalog.json"
    sc = _read_json(sc_path)
    for t in sc.get("tables", []):
        if not isinstance(t, dict):
            continue
        name = str(t.get("name") or "")
        if not name:
            continue
        t.setdefault("ref", _schema_table_ref(name))
    _write_json(sc_path, sc)

    # feature_catalog.json
    fc_path = ARTIFACTS / "feature_catalog.json"
    fc = _read_json(fc_path)
    for f in fc.get("features", []):
        if isinstance(f, dict):
            f.setdefault("ref", "codebase_map_pack/features/#feature-families")
    _write_json(fc_path, fc)

    # label_registry.json
    lr_path = ARTIFACTS / "label_registry.json"
    lr = _read_json(lr_path)
    for l in lr.get("labels", []):
        if isinstance(l, dict):
            l.setdefault("ref", "codebase_map_pack/labels_metrics/#labels")
    _write_json(lr_path, lr)

    # metric_registry.json
    mr_path = ARTIFACTS / "metric_registry.json"
    mr = _read_json(mr_path)
    for m in mr.get("metrics", []):
        if isinstance(m, dict):
            m.setdefault("ref", "codebase_map_pack/labels_metrics/#metrics")
    _write_json(mr_path, mr)

    # contracts.json
    c_path = ARTIFACTS / "contracts.json"
    c = _read_json(c_path)
    for b in c.get("boundaries", []):
        if isinstance(b, dict):
            b.setdefault("ref", "codebase_map_pack/contracts/")
    _write_json(c_path, c)

    # temporal_validity.json
    tv_path = ARTIFACTS / "temporal_validity.json"
    tv = _read_json(tv_path)
    for e in tv.get("entities", []):
        if isinstance(e, dict):
            e.setdefault("ref", "codebase_map_pack/temporal_validity/")
    _write_json(tv_path, tv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
