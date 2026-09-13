# Ardaro agent tools: document checks and advisory utilities

Connect to **Ardaro Receipt Intelligence or Invoice Matching**, inspect a fixed synthetic result, and see the price of a real analysis call. Both runnable examples stop before payment. No account, API key, wallet, model API call, or customer document is needed.

For framework integration, use the tested [LangChain / LangGraph](docs/frameworks/langchain.md), [Vercel AI SDK](docs/frameworks/vercel.md), or [CrewAI](docs/frameworks/crewai.md) adapters. Each connects to the live MCP service and verifies the same two fixed document examples. The [four advisory utility tools](docs/agent-utilities.md) share this endpoint and publish their own free examples, status, and schemas.

| Workflow | Free proof | Paid processing |
| --- | --- | --- |
| Receipt text/extraction → arithmetic and duplicate review | `npm start` | 0.25 USDC |
| Structured invoice + PO → comparison → human review | `npm run demo:invoice` | 0.50 USDC |

Start with the [invoice walkthrough](docs/invoice-workflow.md) if you build purchasing or accounts-payable workflows. The free tier provides fixed examples and schemas; it does not process your own documents for free. Connection does not automatically upgrade to paid calls.

Useful for developers building expense-review agents, bookkeeping intake, and construction back-office workflows. Ardaro provides normalized receipt fields and review signals for arithmetic, confidence, line items, and possible duplicates.

**Not OCR. Not automatic bookkeeping.** Supply extracted receipt text or a supported structured extraction for paid analysis. Ardaro does not read receipt images, post transactions, pay invoices, or access your Ardaro SaaS workspace. A human should review the advisory result before financial action.

## Run the free proof

Prerequisite: Node.js **24.14.0 or newer**. The official MCP SDK is pinned to **1.30.0**, with a checked-in lockfile.

Clone the public example repository, then run:

```sh
git clone https://github.com/ashevilleislove/ardaro-agent-examples.git
cd ardaro-agent-examples
npm ci --ignore-scripts
npm test
npm start
# Or test invoice matching:
npm run demo:invoice
```

`npm test` is offline. `npm start` makes a few requests to the public Ardaro endpoint. The receipt demo:

1. Initializes a Streamable HTTP MCP connection and lists tools.
2. Calls `get_receipt_example` with empty arguments and prints its synthetic input and example output.
3. Submits that same synthetic input to `analyze_receipt` **without payment**, then verifies the x402 payment-required response.
4. Stops. It does not sign, fund a wallet, authorize payment, or retry with a payment.

Both demos return `fundsSpent: 0` and `paidSettlement: "not attempted"`. The invoice demo additionally checks service readiness, validates the fixed result identity, and presents the comparison for human review. The example transport rejects authentication/payment headers, payment metadata, non-Ardaro destinations, and redirects. It accepts no CLI input, reads no environment credentials, and contains no wallet dependency. Do not turn this demonstration guard into a general-purpose payment authorization policy.

No Node installation? Inspect the [public synthetic example](https://agents.getardaro.com/agent-services/receipt-intelligence/example) in a browser. This is a fixed fixture, **not free processing of your own receipt**.

### What the example actually shows

The live synthetic fixture returned a supplier receipt with subtotal `100.00`, tax `7.00`, and total `107.00`. Its expected analysis includes:

```json
{
  "status": "review_required",
  "arithmetic_verified": true,
  "arithmetic_consistency": "verified",
  "duplicate_check": {
    "likely_duplicate": false,
    "decision": "no_exact_match"
  }
}
```

This is a shortened excerpt of the **fixed example's expected response**, not a newly purchased analysis. The full result contains normalized fields, confidence values, line items, and human-review warnings. `no_exact_match` only reflects the supplied comparison fingerprints; it is not a guarantee that a receipt is unique. See [verification notes](VERIFICATION.md).

## Connect an existing MCP client

| Setting | Value |
| --- | --- |
| Endpoint | `https://agents.getardaro.com/mcp` |
| Transport | Streamable HTTP, stateless JSON |
| Free tools | 12 fixed-example and service-status tools; arguments `{}`. See [the complete inventory](docs/agent-utilities.md#tool-inventory). |
| Paid tools | `analyze_receipt` (0.25 USDC), `match_invoice` (0.50 USDC), plus [four advisory utilities](docs/agent-utilities.md) (0.05–0.25 USDC). |
| Authentication for free discovery | None |
| Registry name | `io.github.ashevilleislove/ardaro-receipt-intelligence` |

Enter the endpoint in your client's **remote Streamable HTTP** connection settings. Configuration formats vary; there is no universal JSON config for every MCP application. An ordinary browser GET to `/mcp` can return HTTP 405 because it is a protocol endpoint, not a webpage.

Connecting an MCP client does **not** create a wallet or approve spending. A generic client can run the free example but needs a separate x402-compatible wallet adapter for paid analysis.

## Price and paid integration boundary

One receipt analysis costs **0.25 USDC**, or **250000 atomic units**, on **Base mainnet (`eip155:8453`)**. Invoice matching is 0.50 USDC; the four utility prices are [listed separately](docs/agent-utilities.md). Inspect the current live challenge before approving a purchase; third-party wallet/provider charges, if any, are separate.

For MCP, the unpaid `analyze_receipt` tool result has `isError: true` with an x402 v2 challenge in `structuredContent` and JSON text. This is the expected payment request, not permission to pay. An owner-approved adapter supplies its payment payload in `params._meta["x402/payment"]`. A successful settlement response is returned in result `_meta["x402/payment-response"]`.

The payable resource is the REST URL `https://agents.getardaro.com/v1/receipt-intelligence/analyze`, **not** the MCP transport URL. Before signing, validate the exact HTTPS resource, network, canonical USDC asset, recipient, amount ceiling, expiry, and one stable payment identifier against an owner-approved policy. Keep wallet credentials out of prompts, logs, and this repository. If the outcome is unknown, do not create a fresh payment authorization just to retry.

**Verification scope:** this example verifies the free MCP connection, fixture, and unpaid challenge. Separately, four owner-operated utility REST purchases passed on September 13, 2026 UTC, with response and Base transfer checks recorded in [the evidence](evidence/owner-rest-tests-20260913.json). Those REST tests do not establish paid utility MCP execution or customer adoption. This repository contains no paying MCP implementation.

### Optional manual paid REST call — spends real funds

This separate command is for a developer who already has an authenticated, funded Coinbase Agentic Wallet and explicitly approves this purchase. It is **not** run by `npm start` or `npm test`. Its syntax and atomic-unit cap follow [Coinbase's official pay-for-service documentation](https://docs.cdp.coinbase.com/agentic-wallet/cli/skills/pay-for-service).

Review the [live Ardaro integration instructions](https://agents.getardaro.com/receipt-intelligence/SKILL.md) and wallet policy first. The example below is for **Bash-compatible shells**; do not paste untrusted strings into shell commands.

```bash
npx awal@2.12.1 x402 pay https://agents.getardaro.com/v1/receipt-intelligence/analyze -X POST -d '{"contract_version":"ardaro.agent-receipt-intelligence.request.v1","input":{"kind":"text","text":"Example Supply\nDate: 09/05/2026\nSubtotal: $100.00\nTax: $7.00\nTotal: $107.00"},"existing_fingerprints":[]}' --max-amount 250000 --json
```

This command authorizes an automatic x402 payment up to 0.25 USDC for the request. It is a **REST** integration path, not proof that your MCP client supports payments. The amount cap alone does not replace validating the asset, recipient, resource, and your wallet's spending policy. This optional command was documentation-reviewed and was not executed as part of these client examples.

## Troubleshooting

- **Payment-required / `isError: true`:** expected for unpaid `analyze_receipt`. The demo checks and stops there.
- **HTTP 405 in a browser or optional GET:** use a Streamable HTTP client; the service accepts MCP POST requests.
- **HTTP 429 or timeout:** stop and wait; do not hammer the public endpoint. This demo does not automatically retry.
- **The proof fails:** inspect the error and current [OpenAPI contract](https://agents.getardaro.com/openapi.json). Do not disable the safety checks or attach a wallet just to make the free test pass.
- **Want to send receipt photos?** Extract text first using your own authorized OCR path. Do not send images to this endpoint.
- **Duplicate signals:** provide the fingerprints you are authorized to compare. This is not access to a global database of other customers' receipts.

## Resources and human help

- [Advisory utilities, prices and owner REST test evidence](docs/agent-utilities.md)
- [LangChain / LangGraph adapter](docs/frameworks/langchain.md)
- [Vercel AI SDK adapter](docs/frameworks/vercel.md)
- [CrewAI adapter and Zapier integration scope](docs/frameworks/crewai.md)
- [Invoice workflow and buyer setup](docs/invoice-workflow.md)
- [Invoice public quickstart](https://agents.getardaro.com/invoice-matching)
- [Invoice TypeScript buyer ZIP](https://agents.getardaro.com/invoice-matching/buyer.zip)
- [Receipt TypeScript buyer ZIP](https://agents.getardaro.com/receipt-intelligence/buyer.zip)
- [Ardaro product and integration guide](https://agents.getardaro.com/receipt-intelligence#mcp)
- [Public agent integration instructions](https://agents.getardaro.com/receipt-intelligence/SKILL.md)
- [OpenAPI](https://agents.getardaro.com/openapi.json)
- [Official MCP Registry](https://registry.modelcontextprotocol.io/?q=ardaro)
- [Smithery listing](https://smithery.ai/servers/brent-a8er/ardaro-receipt-intelligence)
- [Official MCP SDK documentation](https://github.com/modelcontextprotocol/typescript-sdk/tree/v1.x)
- [Contact Ardaro's founder on LinkedIn](https://www.linkedin.com/in/theamazinghuman/)

For integration questions, share a **synthetic** reproduction and the error message. Never post real receipts, customer information, wallet keys, payment authorizations, or account credentials in a public issue.

You can also email the founder at [brent@getardaro.com](mailto:brent@getardaro.com).

This repository contains independently authored client examples, not the private Ardaro application or its deployment code. `private: true` in `package.json` prevents accidental npm publication; it does not prevent using these examples or publishing this repository on GitHub.

## License

The client examples and documentation in this repository are [MIT licensed](LICENSE).
This license does not grant rights to the hosted service, Ardaro's private
application, or its branding, and does not make paid service calls free.
