# Security Policy

## Reporting vulnerabilities

Report security issues to [security@akeyless.io](mailto:security@akeyless.io). Do not open public GitHub issues for vulnerabilities.

## Design principles

1. **Credentials never leave the Gateway** — tools return query/action results and secret metadata only.
2. **Customer Gateway required** — ARA execute APIs are not available on `api.akeyless.io`; misconfiguration is rejected in config validation.
3. **Cloud identity by default** — `aws_iam` uses the AgentCore execution role; no long-lived Akeyless access keys in production.
4. **Never log tokens or secret values** — do not print `Authorization` headers, access keys, or dynamic credential payloads.
5. **Least privilege** — bind the auth method to the AgentCore role ARN; scope ARA allow-access to needed paths only.

## Production checklist

- [ ] `AKEYLESS_GATEWAY_URL` points at your org Gateway with ARA enabled
- [ ] `AKEYLESS_ACCESS_TYPE=aws_iam` (not `access_key`)
- [ ] Auth method bound to AgentCore execution role ARN
- [ ] Role has `ara_allow_access` only on intended paths
- [ ] No secrets or access keys in AgentCore env beyond bootstrap Access ID / Gateway URL
