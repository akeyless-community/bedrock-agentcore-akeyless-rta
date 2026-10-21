# Contributing

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[mcp,dev]"
pytest
```

## Guidelines

- Never log or commit credentials, tokens, or `.env` files.
- Prefer new tests over changing existing ones.
- Keep ARA protocol aligned with the Claude/Cursor connectors and Gateway `/config/target_query` contract.
- Do not add a dependency on `akeyless-agentcore-runtime`; this package stays standalone.
