# Deploy RTA MCP on Bedrock AgentCore

## Pattern

Deploy this package as an AgentCore Runtime with **`protocol: MCP`**. Agents discover tools (`list-secrets`, `query-db`, `service-execute`, `list-sub-tools`) over MCP; `service-execute` also runs remote commands on SSH, Windows, and LDAP items (Gateway 5.6.0+). The process authenticates to your Akeyless Gateway and executes ARA calls server-side.

## Bootstrap envVars

Map into `agentcore.json` / Runtime env (no application secrets):

| Name | Example |
|------|---------|
| `AKEYLESS_GATEWAY_URL` | `https://gw.example.com:8000` |
| `AKEYLESS_ACCESS_ID` | `p-xxxxx` |
| `AKEYLESS_ACCESS_TYPE` | `aws_iam` |
| `AKEYLESS_AGENT_ID` | `my-agent` (optional) |

## Entry point

Use `examples/mcp-server/server.py` as the runtime's `main.py`. With AgentCore CLI 1.x:

```bash
agentcore create --name MyRta --template agent-python-minimal
cd MyRta
cp /path/to/examples/mcp-server/server.py app/agent/main.py
# in agentcore/agentcore.json, on the runtime: "protocol": "MCP", "authorizerType": "AWS_IAM", envVars as above
agentcore deploy
```

See the [user guide](USER_GUIDE.md) for the full `agentcore.json` runtime entry.

Add the dependency to `app/agent/pyproject.toml`:

```text
akeyless-agentcore-rta[mcp,aws]>=0.3.0
```

The `aws` extra installs `boto3`, which the `aws_iam` cloud ID needs.

## After deploy

1. Bind the AgentCore execution role on the Akeyless AWS IAM auth method (`--bound-role-name`), then attach the Akeyless role to it.
2. Invoke the MCP runtime and call `list-secrets`.
3. Run a read-only `query-db` only with approval if the payload can change data or incur cost.

## Complementary secrets package

If the same agent also needs a model API key at startup, use [`akeyless-agentcore-runtime`](https://github.com/akeyless-community/bedrock-agentcore-akeyless-runtime) `get_secret()` in-process — do not add get-secret tools to this RTA server.
