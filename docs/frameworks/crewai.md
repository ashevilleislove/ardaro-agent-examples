# CrewAI: two fixed document examples through an explicit adapter

Inspect receipt line items and invoice-to-PO discrepancies using two real CrewAI tools mapped from Ardaro's MCP service. The included adapter selects the fixed free tools before converting schemas, so you can evaluate the results and plan a human review step.

## Run

Tested with **Python 3.11.0**, **CrewAI / crewai-tools 1.15.21**, **MCPAdapt 0.1.19**, and **MCP 1.28.1**:

```sh
cd examples/frameworks/crewai
python -m venv .venv
# macOS / Linux:
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m unittest test_free_fixture_adapter.py test_runtime_guards.py
.venv/bin/python verify_free_adapter.py
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. Run Python normally, without optimization flags. The complete lock captures the tested environment; it is not a cross-platform compatibility guarantee.

The adjacent [connection JSON](../../examples/frameworks/crewai/crewai.connection.json) uses MCPAdapt's Streamable HTTP options:

```json
{"url":"https://agents.getardaro.com/mcp","transport":"streamable-http"}
```

The [custom adapter](../../examples/frameworks/crewai/free_fixture_adapter.py) implements MCPAdapt's `ToolAdapter` interface, skips other tools before schema mapping, and delegates the two empty-input schemas to CrewAI's own `CrewAIToolAdapter`. The [runner](../../examples/frameworks/crewai/verify_free_adapter.py) bounds requests and calls each fixed example once. It writes reports and synthetic results next to the script.

In an existing application, the small adapter can also be used directly:

```python
from free_fixture_adapter import free_fixture_tools

with free_fixture_tools() as (tools, discovered_names):
    for tool in tools:
        fixture_json = tool.run()  # fixed input: {}
```

## Evidence and compatibility

- [September 13 runtime record](../../evidence/frameworks/crewai.json): all 18 catalog names discovered; only `get_receipt_example` and `get_invoice_matching_example` exposed and invoked. Both returned synthetic JSON text.
- The receipt fixture has one line item and total `107.00`; the invoice fixture has one matched line, zero discrepancies, and three uninvoiced PO units. Both require human review.
- Stock `MCPServerAdapter` fails while converting a lookahead regex in the full invoice schema. The working path above uses a custom adapter; it does not rewrite service schemas. See the [scoped failure record](../../evidence/frameworks/crewai-stock-blocker.json).
- [Four utility owner REST tests](../agent-utilities.md#owner-rest-purchase-evidence) establish separate synthetic purchase evidence. This example verifies direct free-tool execution, not a model-driven Crew, paid utility MCP execution, or a native Zapier integration.

The connection pattern follows [CrewAI's Streamable HTTP documentation](https://docs.crewai.com/v1.15.21/en/mcp/streamable-http), using the [MCPAdapt ToolAdapter extension](https://github.com/grll/mcpadapt/blob/main/src/mcpadapt/core.py). The dependency lock identifies the tested implementation versions.
