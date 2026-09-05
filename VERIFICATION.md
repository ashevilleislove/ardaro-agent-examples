# Verification notes

Checked on **September 5, 2026**, using Node.js **24.14.0**, npm **11.9.0**, and the official MCP SDK **1.30.0**.

## Reproducible checks

- `npm ci --ignore-scripts`: completed from the lockfile; 94 installed packages, 95 audited including this package.
- `npm test`: **21 passed**, 0 failed, 0 skipped. Tests use mocks and do not contact production.
- `npm audit --omit=dev --audit-level=low`: **0 reported vulnerabilities** at check time. This is not a guarantee against unknown or future vulnerabilities.
- `npm start`: **passed against the live public MCP endpoint**, once, without a wallet or payment payload.

The live run initialized the connection, discovered `analyze_receipt` and `get_receipt_example`, retrieved the fixed synthetic fixture, and received an unpaid x402 v2 challenge for the REST analysis resource at **250000 atomic USDC units on Base mainnet**. It stopped there.

The result summary was:

```json
{
  "checks": {
    "discovery": "passed",
    "syntheticExample": "passed",
    "unpaidChallenge": "passed"
  },
  "paidSettlement": "not attempted",
  "fundsSpent": 0
}
```

The free fixture contained a synthetic structured receipt and its expected output. It was not a live purchase or analysis of customer data.

## Deliberately not claimed

- No fresh real-money MCP settlement was performed or proven by this repository.
- No wallet was installed, funded, authenticated, or given signing permission.
- No customer adoption, integration, revenue, or commercial demand is established by a successful demo.
- The optional paid REST command in the README was documentation-reviewed, **not executed**.
- The example's no-spend checks are a teaching boundary, not a complete production payment policy or security audit.

For the CLI command's documented options and atomic-unit amount cap, see [Coinbase's official pay-for-service reference](https://docs.cdp.coinbase.com/agentic-wallet/cli/skills/pay-for-service). Consult current service and wallet documentation before making any real payment.
