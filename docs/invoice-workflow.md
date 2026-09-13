# Try invoice-to-PO comparison without a wallet

Use this when you already have structured invoice and purchase-order data and want a review step between extraction and accounting. Ardaro compares explicit line references or unique exact product codes, quantities, unit prices and supplied arithmetic. The result remains advisory.

```text
Your extraction / purchasing system
                ↓
Structured invoice + purchase order
                ↓
Ardaro match_invoice (buyer-authorized paid operation)
                ↓
Comparison rows, discrepancies and unknowns
                ↓
Human review in your own application
```

## 1. Run the fixed free proof

From the repository folder, with Node.js 24.14.0+:

```sh
npm ci --ignore-scripts
npm test
npm run demo:invoice
```

This command calls the public MCP endpoint at `https://agents.getardaro.com/mcp`. It checks readiness, gets the fixed invoice/PO example, checks the example result hash and requests an **unsigned** 0.50-USDC payment challenge. It then stops. It does not accept document arguments, run a model, sign, fund a wallet, submit payment metadata or retry with payment.

The example invoice bills two boards at 10.00 each against a PO for five. The expected result matches one line and reports no discrepancies for the supported checks. Three units remain uninvoiced **within this single comparison**; that does not establish whether goods were delivered or previously invoiced. `human_review_required` remains true and `payment_approved` remains false.

Look for:

```json
{
  "checks": {
    "discovery": "passed",
    "serviceStatus": "passed",
    "syntheticExample": "passed",
    "resultIdentity": "passed",
    "unpaidChallenge": "passed"
  },
  "paidSettlement": "not attempted",
  "fundsSpent": 0
}
```

The output includes the complete fixed request/result and a `reviewHandoff` object. It is not a fresh paid analysis. The hash checks result consistency; it does not authenticate documents.

## 2. Check the input mapping

Inspect the current schema through `tools/list` or [invoice OpenAPI](https://agents.getardaro.com/invoice-matching/openapi.json). Both documents need references, currency, supplier identifiers and line items. The invoice identifies the PO. Use decimal strings for quantities and prices; preserve line IDs and units. Include supplied line amounts and invoice totals for complete arithmetic checks.

The service accepts one invoice and one PO, at most 100 lines each. It does not extract images, verify delivery, reconcile prior invoices, determine tax, approve payments or post to accounting. If your source is a PDF or photograph, perform extraction through your own authorized system first.

## 3. Use the existing paid buyer when ready

Download the [invoice TypeScript buyer](https://agents.getardaro.com/invoice-matching/buyer.zip) and follow its bundled README. It includes the paid MCP implementation, pinned dependencies, schemas and synthetic tests. In that separate package, `npm ci --ignore-scripts`, `npm run typecheck` and `npm test` do not make paid calls.

Your application supplies an existing authorized signer, independently verified merchant address, stable logical request ID, request body and explicit approval callback. An ordinary MCP client alone has no payment capability. The quote must match exactly **500000 atomic native USDC units on Base (`eip155:8453`)**, the invoice resource, and your pinned merchant. Discovering tools or running the free proof is not spending authorization.

The paid MCP operation is `match_invoice`. The signed resource is `https://agents.getardaro.com/v1/invoice-matching/analyze`. If an outcome becomes unknown, preserve the original operation and follow its exact-payment recovery instructions; do not create a new signature to retry. Retain validated responses for your application's human review according to its data policy.

## 4. Give useful integration feedback

Email [brent@getardaro.com](mailto:brent@getardaro.com) with your framework, the failing step, and a synthetic input shape. Tell us whether the missing piece is source-field mapping, review output, wallet setup or recovery. Do not send customer invoices, wallet keys or signed payment payloads.

Free examples and internal acceptance tests demonstrate a technical path. They do not establish outside-customer adoption or token savings. See [verification notes](../VERIFICATION.md).
