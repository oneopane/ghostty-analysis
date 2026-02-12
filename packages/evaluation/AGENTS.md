# PROJECT KNOWLEDGE BASE

## OVERVIEW
Offline evaluation harness for routing and policy signals, consuming inference artifacts and history DBs.

## STRUCTURE
```
packages/evaluation/
├── src/evaluation_harness/
│   ├── cli/
│   ├── runner.py
│   ├── metrics/
│   ├── reporting/
│   ├── sampling.py
│   ├── cutoff.py
│   ├── store/
│   └── config.py
└── tests/
```

## COMMANDS
```bash
uv run --project packages/evaluation evaluation run --repo owner/name
uv run --project packages/evaluation evaluation show --repo owner/name --run-id run1
uv run --project packages/evaluation evaluation explain --repo owner/name --run-id run1 --pr 123
```
