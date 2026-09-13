# Verification notes

## Utility evidence and framework adapters — September 13, 2026 UTC

Three framework-specific examples were executed against `https://agents.getardaro.com/mcp`, reporting server `ardaro-agent-services` version **1.3.0**. Each discovered the 18-tool catalog and invoked the two fixed document examples. Each run used empty tool arguments and performed no model, wallet, or paid tool operation.

| Adapter | Pinned versions | Live result and scope |
| --- | --- | --- |
| [LangChain MCPAdapter](docs/frameworks/langchain.md) | Python 3.11.0; LangChain 1.4.0; FastMCP 4.0.3; MCP 2.2.0 | [PASS](evidence/frameworks/langchain.json): both fixed examples and canonical result identities. A LangGraph execution was not run. |
| [Vercel AI SDK MCP](docs/frameworks/vercel.md) | Node 24.14.0; `@ai-sdk/mcp` 2.0.49; Zod 4.1.8 | [PASS](evidence/frameworks/vercel.json): explicit free-tool schemas; both examples and canonical result identities. |
| [CrewAI custom free-only adapter](docs/frameworks/crewai.md) | Python 3.11.0; CrewAI / crewai-tools 1.15.21; MCPAdapt 0.1.19; MCP 1.28.1 | [PASS](evidence/frameworks/crewai.json): two mapped CrewAI tools invoked directly. A model-driven Crew was not run. |

The stock CrewAI `MCPServerAdapter` failed during full-catalog schema conversion because its Rust regex validator rejects lookahead. The working example uses MCPAdapt's custom `ToolAdapter` interface to select the two fixed tools before conversion. Thirteen offline boundary tests cover tool selection, argument/error handling, payment metadata rejection, and the request limit. LangChain's FastMCP validator also warns that it skips unsupported lookahead patterns; the passing run is not proof of full client-side schema conformance.

Existing repository checks were rerun for this publication: `npm ci --ignore-scripts` succeeded, **33 offline tests passed**, and both `npm start` and `npm run demo:invoice` passed their live discovery, synthetic fixture, and unsigned payment-challenge checks. Neither demo submitted payment. Python locks capture the tested Python 3.11 environments; other platforms and package versions need their own checks.

Separately, [four owner-operated synthetic utility REST tests](evidence/owner-rest-tests-20260913.json) passed exact response and Base transfer checks. Total **0.55 USDC** comprises the earlier 0.10 budget test plus the later three tests totaling 0.45. The evidence links public transfer receipts and distinguishes them from publisher-recorded response validation. Paid utility MCP execution, customer adoption, and product performance benchmarks remain outside these tests.

The prior receipt and invoice verification records below are preserved as historical checks.

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
