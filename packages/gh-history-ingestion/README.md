
# gh-history-ingestion

Repository-agnostic GitHub history dataset builder.

## Authentication
Default auth uses the GitHub CLI token when available. It falls back to the
`GITHUB_TOKEN` environment variable.

### GitHub CLI (recommended)
1. `gh auth login`
2. The CLI token is used automatically.

### Environment variable
Set a token manually if you prefer:

```bash
export GITHUB_TOKEN="ghp_..."
```
