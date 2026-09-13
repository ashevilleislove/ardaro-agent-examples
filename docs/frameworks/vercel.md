# Vercel AI SDK: inspect receipt and invoice fixtures

Connect the AI SDK MCP client to Ardaro and inspect normalized receipt line items and invoice-to-PO exceptions through two fixed examples. This runnable check uses explicit schemas for those free tools, leaving your application's model and purchase decisions separate.

## Run

Tested with **Node 24.14.0**, **`@ai-sdk/mcp` 2.0.49**, and **Zod 4.1.8**:

```sh
cd examples/frameworks/vercel
npm ci --ignore-scripts
npm run verify
```

The adjacent [connection JSON](../../examples/frameworks/vercel/vercel.connection.json) is passed to `createMCPClient`:

```json
{"transport":{"type":"http","url":"https://agents.getardaro.com/mcp"}}
```

The [executable adapter](../../examples/frameworks/vercel/verify-free.mjs) fixes the destination, bounds requests, rejects payment metadata, and exposes only `get_receipt_example` and `get_invoice_matching_example` through explicit empty input schemas. It executes each with `{}`, verifies the synthetic marker and result identity, then closes the client. Reports are written in the current directory. No model provider is needed.

## Evidence and scope

- [September 13 runtime record](../../evidence/frameworks/vercel.json): service 1.3.0 exposed 18 tools; the two fixed examples passed canonical result identity checks.
- The receipt fixture has one line item and total `107.00`. The invoice fixture has one matched line, zero discrepancies, and three uninvoiced PO units. Both remain subject to human review.
- The tested SDK handled optional discovery/GET responses and completed the normal MCP initialize flow. A browser GET to `/mcp` is not a service webpage.
- [Four utility owner REST tests](../agent-utilities.md#owner-rest-purchase-evidence) separately establish synthetic paid REST acceptance. This adapter invokes no paid tool or model.

Configuration follows [Vercel's MCP tools documentation](https://ai-sdk.dev/docs/ai-sdk-core/mcp-tools). See [utility scope and prices](../agent-utilities.md) for processing supplied data.
