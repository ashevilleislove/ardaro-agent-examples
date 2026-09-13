# Verification notes

## Invoice quickstart update — September 12, 2026 (America/New_York)

- Node.js 24.14.0 and npm 11.9.0; MCP SDK remains pinned to 1.30.0. No new dependency was added.
- `npm test`: **33 passed**, including invoice review policy, result-identity tampering, incorrect quotes, closed readiness, and payment-metadata rejection before network access.
- `npm audit --omit=dev --audit-level=low`: zero reported vulnerabilities at this check.
- `npm run demo:invoice`: passed against the public MCP endpoint. Five checks passed: discovery, readiness, fixed synthetic example, example result identity and unsigned x402 challenge for 500000 atomic native USDC units on Base.
- `npm start`: existing receipt proof still passes against production.
- Both live runs returned `fundsSpent: 0` and `paidSettlement: "not attempted"`. No wallet, model call, customer input or signed payment was used.
- `test/fixtures/invoice-example.json` and `invoice-status.json` are public service snapshots used only by offline tests. The status snapshot is not a live availability or settlement claim.
- The invoice handoff retains human review even for `no_discrepancies`. The paid buyer is linked as a separate package; it is not executed by these examples.

The original receipt-only verification follows as historical evidence.

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
