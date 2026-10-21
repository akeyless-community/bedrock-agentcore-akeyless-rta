# Deploy RTA MCP on Bedrock AgentCore

## Pattern

Deploy this package as an AgentCore Runtime with **`protocol: MCP`**. Agents discover tools (`list-secrets`, `query-db`, `service-execute`, `list-sub-tools`) over MCP. The process authenticates to your Akeyless Gateway and executes ARA calls server-side.

## Bootstrap envVars

Map into `agentcore.json` / Runtime env (no application secrets):

| Name | Example |
|------|---------|
| `AKEYLESS_GATEWAY_URL` | `https://gw.example.com:8000` |
| `AKEYLESS_ACCESS_ID` | `p-xxxxx` |
| `AKEYLESS_ACCESS_TYPE` | `aws_iam` |
| `AKEYLESS_AGENT_ID` | `my-agent` (optional) |

## Entry point

Use `examples/mcp-server/server.py`:

```bash
agentcore configure -e examples/mcp-server/server.py --protocol MCP
agentcore deploy
```

Install from PyPI (AgentCore packaging prefers wheels over `git+https`):

```text
akeyless-agentcore-rta[mcp]>=0.1.0
```

## After deploy

1. Bind the AgentCore execution role ARN on the Akeyless AWS IAM auth method.
2. Invoke the MCP runtime and call `list-secrets`.
3. Run a read-only `query-db` only with approval if the payload can change data or incur cost.

## Complementary secrets package

If the same agent also needs a model API key at startup, use [`akeyless-agentcore-runtime`](https://github.com/akeyless-community/bedrock-agentcore-akeyless-runtime) `get_secret()` in-process — do not add get-secret tools to this RTA server.
