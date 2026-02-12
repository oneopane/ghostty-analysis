# Import-path routers for LLM experimentation (stub)

Use `RouterSpec(type="import_path", import_path="pkg.mod:factory")` to load custom routers without changing core packages.

Guidelines:
- Keep core `inference` offline and dependency-light.
- Put LLM client dependencies in your external package.
- Enforce leakage safety by only using `PRInputBundle` content built as-of cutoff.
- Persist large prompt/response payloads under `prs/<pr>/llm/<router>/<step>.json` and keep only hashes/references in `Evidence.data`.

Factory shape:

```python
# pkg/mod.py
from repo_routing.registry import PredictorRouterAdapter

def create_router(config_path: str | None = None):
    predictor = ...  # your FeatureExtractor/Ranker pipeline
    return PredictorRouterAdapter(predictor=predictor)
```

Built-in example in this repo:
- import path: `repo_routing.examples.llm_router_example:create_router`
- optional config JSON:

```json
{
  "model_name": "dummy-llm-v1",
  "mention_boost": 2.0,
  "review_request_boost": 1.5,
  "area_overlap_boost": 0.5
}
```

Then run with evaluation:

```bash
evaluation run \
  --repo owner/name \
  --router-import repo_routing.examples.llm_router_example:create_router \
  --router-config config.json
```
