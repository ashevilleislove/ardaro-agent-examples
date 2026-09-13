# Advisory utilities for agent workflows

Ardaro exposes receipt normalization, invoice-to-PO comparison, and four small deterministic utilities through **`https://agents.getardaro.com/mcp`**. Connect with Streamable HTTP, inspect a fixed example, and apply your own human-review and purchase policy before processing supplied data.

| Tool | Result to review | USDC per accepted analysis | REST segment |
| --- | --- | --- | --- |
| `compress_agent_context` | A candidate that reduces runs of three or more line breaks to two | 0.05 | `context-compression` |
| `route_model_intent` | A bounded keyword classification for structured-calculation or general-text review | 0.15 | `intent-routing` |
| `authorize_agent_spend` | Proposed downstream cost compared with caller-supplied limits and history | 0.10 | `budget-check` |
| `reconcile_api_ledger` | Supplied billing and usage records compared by request ID, exact amount and currency | 0.25 | `ledger-reconciliation` |

The context candidate needs review where whitespace carries meaning. Intent classification provides an advisory label; model selection and execution remain with the caller. The spending check evaluates unauthenticated supplied records and grants no spending authority or reservation. Its comparison excludes its own 0.10 USDC service fee, and an unfavorable result remains a billable analysis. Ledger comparison checks supplied records rather than proving service delivery. All four results require human review.

## Free entry point

For any tool above, call `get_<tool>_service_status` and `get_<tool>_example` with `{}`. A fixed example shows the request shape and expected result. For example:

```json
{
  "jsonrpc": "2.0",
  "id": "budget-example",
  "method": "tools/call",
  "params": {
    "name": "get_authorize_agent_spend_example",
    "arguments": {}
  }
}
```

Send this through an initialized MCP client. The three [framework adapters](../README.md#resources-and-human-help) handle connection lifecycle and verify fixed receipt and invoice examples without attaching a wallet or invoking a model. Their successful free execution is separate from the utility REST purchase evidence below.

For a REST segment in the table, public reads are:

```text
https://agents.getardaro.com/v1/agent-utilities/<segment>/status
https://agents.getardaro.com/v1/agent-utilities/<segment>/example
https://agents.getardaro.com/v1/agent-utilities/<segment>/openapi.json
```

The payable resource ends in `/analyze`. Fixed examples and schema reads do not process arbitrary caller input.

## Owner REST purchase evidence

On **September 13, 2026 UTC**, the owner signed one synthetic REST purchase for each utility. All four returned HTTP 200 and passed response schema, canonical result identity, exact expected outcome, payment binding, and exact Base USDC transfer checks.

| Tool | USDC | Public transaction |
| --- | --- | --- |
| `compress_agent_context` | 0.05 | [Base receipt](https://basescan.org/tx/0xd133983ce4e0de4bccbe7884f9a966662290498bf3643b7901cc58641f708ed9) |
| `route_model_intent` | 0.15 | [Base receipt](https://basescan.org/tx/0x800d15f27f585d08ff7055155f3d56ac4dd40ec409777adcb8e982efd680e6fc) |
| `authorize_agent_spend` | 0.10 | [Base receipt](https://basescan.org/tx/0xb84dc8ab7eae131f0bce1f311d0748d1cb88891311b183d1681136a444403dda) |
| `reconcile_api_ledger` | 0.25 | [Base receipt](https://basescan.org/tx/0x9dc6cec685cbd8024d78b335a972a30a85ea6960d6a1841401933e1325b677fb) |

The combined owner test amount is **0.55 USDC**: the earlier budget test was 0.10 and the later three tests totaled 0.45. The [sanitized evidence](../evidence/owner-rest-tests-20260913.json) records timestamps, transport, transfer receipts, and local acceptance checks. A chain transaction proves the transfer; response-validation results are the publisher's separate recorded checks. These tests establish owner-operated synthetic REST acceptance, not paid utility MCP execution, a customer deployment, or a performance benchmark.

## Paid caller boundary

A paid request needs explicit authority and an x402-capable signer. Check the current service challenge for the exact REST resource, `eip155:8453`, native USDC, recipient, amount, expiry, and payment identifier. MCP payment metadata belongs in `params._meta["x402/payment"]`; the settlement receipt belongs in `result._meta["x402/payment-response"]`. A result or challenge alone is not permission to spend.

If payment outcome is uncertain, preserve the identical request, signed payment and payment identifier. Follow the [public integration contract](https://agents.getardaro.com/agent-utilities/SKILL.md), [terms](https://getardaro.com/legal/terms), and [privacy notice](https://getardaro.com/legal/privacy).

## Tool inventory

The verified 1.3.0 catalog has six paid tools and twelve free tools. Alongside the four utility pairs above:

| Service | Paid tool | Fixed example | Status |
| --- | --- | --- | --- |
| Receipt Intelligence | `analyze_receipt` | `get_receipt_example` | `get_receipt_service_status` |
| Invoice Matching | `match_invoice` | `get_invoice_matching_example` | `get_invoice_matching_service_status` |

Inspect the current [service catalog](https://agents.getardaro.com/agent-services) and [utility quickstart](https://agents.getardaro.com/agent-utilities) for availability. Custom A2A discovery is outside these MCP examples.
