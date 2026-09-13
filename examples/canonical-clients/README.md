# Canonical-schema clients for Ardaro

These explicit adapters construct all 18 live Ardaro tool definitions in CrewAI, LangChain and Vercel AI SDK without flattening JSON Schema unions, stripping constraints, or converting strict patterns through a lossy schema generator. They validate inputs before transport and validate each declared output schema. Eight tools do not declare an output schema; this absence is preserved.

The default execution policy permits only `get_receipt_example` and `get_invoice_matching_example`, two fixed synthetic fixtures. All paid tools remain disabled. Discovering a paid tool does not authorize spending. A production paid client requires a separate, explicitly approved x402 implementation; these adapters contain no wallet signer.

Endpoint: `https://agents.getardaro.com/mcp`, Streamable HTTP. Fetch the current catalog before constructing adapters; the checked-in fixture is a dated regression reference, not an automatically refreshed catalog.

## Run

Use separate Python environments because the tested CrewAI and LangChain releases use different MCP dependency versions. Set `OTEL_SDK_DISABLED=true`, `CREWAI_DISABLE_TELEMETRY=true`, `LANGSMITH_TRACING=false`, `LANGCHAIN_TRACING_V2=false` and `DO_NOT_TRACK=1` for verification. The supplied verification scripts set these before importing clients.

```sh
# CrewAI environment, Python 3.11
python -m pip install crewai==1.15.21 crewai-tools==1.15.21 mcpadapt==0.1.19 mcp==1.28.1 pydantic==2.12.5 jsonschema==4.26.0 httpx==0.28.1
python -m unittest test_canonical
python verify_python.py --framework crewai --output ./crewai-verification

# Separate LangChain environment, Python 3.11
python -m pip install langchain==1.4.0 langchain-core==1.6.3 fastmcp==4.0.3 mcp==2.2.0 pydantic==2.13.5 jsonschema==4.26.0 httpx2==2.12.0 httpx==0.28.1
python -m unittest test_canonical
python verify_python.py --framework langchain --output ./langchain-verification

# Vercel AI SDK, Node.js 24+
npm ci --ignore-scripts
npm test
node verify-vercel.mjs ./vercel-verification
```

Run from this directory. Each output directory must be new. Offline tests exercise 54 input cases, the ten declared output schemas, invalid-input rejection and the default paid-call block. Python tests skip the framework absent from that environment; run both environments for both native adapters. Live scripts make bounded anonymous discovery reads and exactly two fixed-example calls, with no model call or payment.

## Use the adapters

- CrewAI: pass `crewai_adapter(current_tools)` to `mcpadapt.core.MCPAdapt`, then use its native tools. The custom adapter replaces only the conversion boundary; it does not patch CrewAI globally or repair its stock schema converter.
- LangChain: call `langchain_tools(current_tools, async_call_tool)`. The callback receives a tool name and validated arguments and must return the MCP result. The wrapper uses native `StructuredTool` definitions.
- Vercel AI SDK: call `createCanonicalTools(client, await client.listTools())`. It supplies unchanged schemas and Ajv validation to native AI SDK tools.

Treat a changed catalog as a new contract to review. No adapter promises compatibility with untested future framework releases. Error results remain errors. Schema validation is not permission to post to accounting, alter a workspace, pay an invoice, or access customer data.
