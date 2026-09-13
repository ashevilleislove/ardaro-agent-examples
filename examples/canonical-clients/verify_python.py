"""Bounded live native-client verification: discovery + two fixed examples only."""
import os
os.environ.update(OTEL_SDK_DISABLED="true", CREWAI_DISABLE_TELEMETRY="true",
                  LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", DO_NOT_TRACK="1")
import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
from datetime import datetime, timezone
from pathlib import Path
import platform

import httpx
from canonical_mcp import ENDPOINT, FREE_EXAMPLES, crewai_adapter, langchain_tools


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify_fixture(fixture):
    assert fixture["synthetic_only"] is True
    response = fixture.get("expected_response", fixture.get("response"))
    assert response["status"] == "review_required"
    assert response["identities"]["analysis_result_identity"] == "res_" + digest(response["result"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework", choices=("crewai", "langchain"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    expected = json.loads((Path(__file__).parent / "fixtures/tools-list.json").read_text())["result"]["tools"]
    calls, observed, results = [], [], {}
    report = {"status": "FAIL", "framework": args.framework, "started_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": ENDPOINT, "python": platform.python_version(), "model_calls": 0, "paid_tool_calls": 0,
        "wallet_operations": 0, "scope": "18 canonical native tool definitions; live execution of two fixed free fixtures only",
        "schema_count": 18, "declared_output_schema_count": 10, "output_schema_absent_count": 8,
        "stock_crewai_adapter_repaired": False, "adapter": "explicit canonical JSON Schema validator"}
    package_names = ["jsonschema", "mcp", "pydantic"] + (
        ["crewai", "crewai-tools", "mcpadapt", "httpx"] if args.framework == "crewai" else
        ["langchain", "langchain-core", "fastmcp", "httpx2"])
    report["packages"] = {name: version(name) for name in package_names}
    http_module = httpx
    if args.framework == "langchain":
        import httpx2
        http_module = httpx2
    native_send = http_module.AsyncClient.send

    def deny(*unused, **kwargs):
        raise AssertionError("Unapproved HTTP client blocked")

    async def async_deny(*unused, **kwargs):
        raise AssertionError("Unapproved HTTP client blocked")

    async def guard(self, request, **kwargs):
        assert str(request.url) == ENDPOINT, "Endpoint blocked"
        assert len(calls) < 20, "Request bound exceeded"
        assert not any(any(token in k.lower() for token in ("authorization", "payment", "api-key")) for k in request.headers)
        rpc = None
        if request.method == "POST":
            rpc = json.loads(await request.aread())
            assert rpc["method"] in {"server/discover", "initialize", "notifications/initialized", "tools/list", "tools/call", "ping"}
            meta = rpc.get("params", {}).get("_meta") or {}
            assert isinstance(meta, dict)
            if rpc["method"] == "server/discover":
                # Inspected MCP 2.2.0 discovery stamps public client/protocol
                # metadata before falling back to the server's older handshake.
                assert set(meta) <= {"io.modelcontextprotocol/protocolVersion",
                    "io.modelcontextprotocol/clientInfo", "io.modelcontextprotocol/clientCapabilities"}
            else:
                assert set(meta) <= {"progressToken"}
                if "progressToken" in meta:
                    assert type(meta["progressToken"]) in (str, int)
            assert len(json.dumps(meta)) < 4096
            if rpc["method"] == "tools/call":
                assert set(rpc["params"]) <= {"name", "arguments", "_meta"}
                assert rpc["params"]["name"] in FREE_EXAMPLES and rpc["params"].get("arguments", {}) == {}
                assert not any(c.get("tool") == rpc["params"]["name"] for c in calls)
        else:
            assert request.method in {"GET", "DELETE"}
        entry = {"method": request.method, "rpc_method": rpc.get("method") if rpc else None,
                 "tool": rpc["params"]["name"] if rpc and rpc["method"] == "tools/call" else None}
        calls.append(entry)
        kwargs["follow_redirects"] = False
        response = await native_send(self, request, **kwargs)
        entry["http_status"] = response.status_code
        if rpc and rpc["method"] in {"initialize", "tools/list", "tools/call"} and response.status_code == 200:
            body = await response.aread()
            assert len(body) <= 2_097_152
            value = json.loads(body)
            if rpc["method"] == "tools/list":
                assert value["result"]["tools"] == expected, "Live catalog differs from captured contract"
                observed.append(value)
            if rpc["method"] == "initialize":
                report["server_info"] = value["result"]["serverInfo"]
                report["protocol_version"] = value["result"]["protocolVersion"]
        return response

    httpx.Client.send = deny
    httpx.AsyncClient.send = async_deny
    http_module.Client.send = deny
    http_module.AsyncClient.send = guard

    try:
        if args.framework == "crewai":
            from mcpadapt.core import MCPAdapt
            client = MCPAdapt({"url": ENDPOINT, "transport": "streamable-http"},
                crewai_adapter(expected), connect_timeout=40, client_session_timeout_seconds=15.0)
            try:
                client.start()
                tools = client.tools()
                assert len(tools) == 18
                for tool in tools:
                    definition = next(d for d in expected if d["name"] == tool.name)
                    assert tool.args_schema.model_json_schema() == definition["inputSchema"]
                    if tool.name in FREE_EXAMPLES:
                        fixture = tool.run()
                        verify_fixture(fixture)
                        results[tool.name] = fixture
            finally:
                client.close()
        else:
            from langchain.mcp import MCPAdapter
            async def run():
                async with MCPAdapter({"mcpServers": {"ardaro": {"url": ENDPOINT}}}) as adapter:
                    remote = await adapter.client.list_tools()
                    assert len(remote) == 18 and observed
                    async def call(name, arguments):
                        return await adapter.client.call_tool(name, arguments, raise_on_error=False)
                    tools = langchain_tools(expected, call)
                    assert len(tools) == 18
                    for tool in tools:
                        definition = next(d for d in expected if d["name"] == tool.name)
                        assert tool.args_schema == definition["inputSchema"]
                        if tool.name in FREE_EXAMPLES:
                            fixture = await tool.ainvoke({})
                            verify_fixture(fixture)
                            results[tool.name] = fixture
            asyncio.run(asyncio.wait_for(run(), timeout=90))
        assert observed and set(results) == FREE_EXAMPLES
        assert len([c for c in calls if c["rpc_method"] == "tools/call"]) == 2
        report.update(status="PASS_FULL_CATALOG_FREE_ONLY", canonical_tools_sha256=digest(expected),
                      canonical_schemas_unchanged=True, live_free_examples=list(results))
    except BaseException as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report.update(finished_at=datetime.now(timezone.utc).isoformat(), calls=calls)
        for name, value in (("execution-report.json", report), ("free-results.json", results), ("tools-list.json", observed)):
            (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
