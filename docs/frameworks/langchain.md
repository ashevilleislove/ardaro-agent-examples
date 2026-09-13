# LangChain / LangGraph: inspect document review results

Use LangChain's MCP adapter to retrieve Ardaro's normalized receipt line items and invoice-to-PO discrepancies before you design a review step in a graph. The runnable example discovers the public catalog, invokes two fixed synthetic tools, and verifies each result identity.

## Run

Tested with **Python 3.11.0**, **LangChain 1.4.0**, FastMCP 4.0.3 and MCP 2.2.0. Use the pinned environment in `examples/frameworks/langchain`:

```sh
cd examples/frameworks/langchain
python -m venv .venv
# macOS / Linux:
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python verify_free.py
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Run Python normally, without optimization flags, so the demonstration's assertions remain active. The full transitive lock records the environment that passed; it is not a cross-platform compatibility guarantee.

The adjacent [connection JSON](../../examples/frameworks/langchain/langchain.connection.json) is passed to `langchain.mcp.MCPAdapter`:

```json
{"mcpServers":{"ardaro":{"url":"https://agents.getardaro.com/mcp"}}}
```

The [executable adapter](../../examples/frameworks/langchain/verify_free.py) includes lifecycle handling, a request boundary, free-tool allowlisting, and result checks. A connection JSON alone does not run an agent or graph. Only `get_receipt_example` and `get_invoice_matching_example` are invoked, both with `{}`. Reports are written next to the script.

## Evidence and scope

- [September 13 runtime record](../../evidence/frameworks/langchain.json): 18 tools discovered from service 1.3.0; both fixed examples invoked and their canonical result identities verified.
- The receipt fixture includes one line item and total `107.00`; the invoice fixture includes one matched line, zero discrepancies, and three uninvoiced PO units. Both are advisory examples for human review.
- FastMCP's Rust validator warns that it skips unsupported regex lookahead patterns. The example checks the result hash and review status; this is not full client-side validation of every service schema.
- [Four utility owner REST tests](../agent-utilities.md#owner-rest-purchase-evidence) separately establish synthetic paid REST acceptance. This adapter run contains no paid tool, model, or LangGraph execution.

This uses the current [LangChain MCPAdapter documentation](https://docs.langchain.com/oss/python/langchain/mcp). Inspect the [service contracts and utility scope](../agent-utilities.md) before introducing supplied data or a payment adapter.
