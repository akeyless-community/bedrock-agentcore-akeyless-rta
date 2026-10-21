# Akeyless setup for AgentCore RTA/ARA

Do this before deploying the MCP server.

## 1. Gateway with ARA

You need a **customer or self-hosted Akeyless Gateway** with Agentic Runtime Authority enabled and AI Insights / ARA configured per [product docs](https://docs.akeyless.io/docs/agentic-runtime-authority).

Set:

```bash
export AKEYLESS_GATEWAY_URL=https://<your-gateway-host>:8000
```

Do **not** use `https://api.akeyless.io` — the public SaaS API does not host ARA execute endpoints. This library rejects that host.

## 2. Auth method (AWS IAM for AgentCore)

```bash
akeyless auth-method create aws-iam \
  --name agentcore-rta \
  --bound-aws-account-id <account-id>
```

AgentCore creates the execution role ARN on **first deploy**. Start with a broader bind (account / later-tightened role ARN), deploy once, then restrict `--bound-aws-role-arn` to the AgentCore role. Same chicken-and-egg as the secrets runtime package.

Local testing can use `access_key` against the same Gateway.

## 3. RBAC — ARA allow access

Grant the auth method’s associated role:

- List / Read on the secret paths you will expose
- An **Agentic Runtime Authority** rule with **Allow Access** (`ara_allow_access`) on those paths

Enable ARA on each dynamic/rotated secret in the Console (or equivalent API).

## 4. Secrets

Store database and service producers under paths your role can see. Custom MCP static secrets appear as `target_type: custom-mcp` in `list-secrets`.

## 5. Verify

```bash
export AKEYLESS_GATEWAY_URL=https://gw.example.com:8000
export AKEYLESS_ACCESS_TYPE=access_key
export AKEYLESS_ACCESS_ID=p-xxxxx
export AKEYLESS_ACCESS_KEY=...

python -c "from akeyless_agentcore_rta import AkeylessRtaClient; print(AkeylessRtaClient().list_secrets())"
```

You should see secret **names and target types** only — never passwords or keys.
