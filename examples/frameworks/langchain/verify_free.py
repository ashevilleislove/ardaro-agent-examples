"""Run LangChain MCPAdapter discovery and two fixed synthetic example tools only."""
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

os.environ.update(OTEL_SDK_DISABLED="true", LANGCHAIN_TRACING_V2="false", LANGSMITH_TRACING="false", DO_NOT_TRACK="1", ANONYMIZED_TELEMETRY="false")
for key in tuple(os.environ):
    if key.endswith("API_KEY") or key.startswith(("LANGSMITH_API", "LANGCHAIN_API")):
        os.environ.pop(key, None)

import httpx
import httpx2

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://agents.getardaro.com/mcp"
FREE = ("get_receipt_example", "get_invoice_matching_example")
calls = []
native_send = httpx2.AsyncClient.send

def deny(*args, **kwargs):
    raise AssertionError("Non-MCP HTTP client blocked")

async def async_deny(*args, **kwargs):
    raise AssertionError("Non-MCP HTTP client blocked")

async def guarded_send(self, request, **kwargs):
    assert str(request.url) == ENDPOINT, "Only the exact public MCP endpoint is allowed"
    assert len(calls) < 20, "Request bound exceeded"
    assert not any(any(word in key.lower() for word in ("authorization", "payment", "api-key")) for key in request.headers), "Credential/payment header blocked"
    rpc = None
    if request.method == "POST":
        rpc = json.loads(await request.aread())
        assert rpc.get("method") in {"server/discover", "initialize", "notifications/initialized", "tools/list", "tools/call", "ping"}, "RPC blocked"
        assert "x402" not in json.dumps(rpc.get("params", {}).get("_meta", {})), "Payment metadata blocked"
        if rpc["method"] == "tools/call":
            assert rpc["params"]["name"] in FREE
            assert rpc["params"].get("arguments", {}) == {}
            assert not any(c.get("tool") == rpc["params"]["name"] for c in calls), "Only one call per example"
    else:
        assert request.method in {"GET", "DELETE"}
    entry = {"http_method": request.method, "rpc_method": rpc.get("method") if rpc else None,
             "tool": rpc["params"]["name"] if rpc and rpc["method"] == "tools/call" else None}
    calls.append(entry)
    kwargs["follow_redirects"] = False
    response = await native_send(self, request, **kwargs)
    entry["http_status"] = response.status_code
    return response

httpx2.AsyncClient.send = guarded_send
httpx2.Client.send = deny
httpx.AsyncClient.send = async_deny
httpx.Client.send = deny

from langchain.mcp import MCPAdapter

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def verify_fixture(fixture):
    assert fixture["synthetic_only"] is True
    response = fixture.get("expected_response", fixture.get("response"))
    assert response["status"] == "review_required"
    expected = "res_" + hashlib.sha256(canonical(response["result"]).encode("utf-8")).hexdigest()
    assert response["identities"]["analysis_result_identity"] == expected

async def main():
    config = json.loads((ROOT / "langchain.connection.json").read_text(encoding="utf-8"))
    assert config == {"mcpServers": {"ardaro": {"url": ENDPOINT}}}
    report = {"framework": "LangChain MCPAdapter", "status": "FAIL", "endpoint": ENDPOINT,
              "started_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "packages": {name: importlib.metadata.version(name) for name in ("langchain", "langchain-core", "fastmcp", "mcp", "httpx2")},
              "model_calls": 0, "paid_tool_calls": 0, "wallet_operations": 0, "cost_usdc": "0.00"}
    results = {}
    try:
        async with MCPAdapter(config) as adapter:
            tools = await adapter.list_tools()
            report["discovered_tool_names"] = [tool.name for tool in tools]
            report["discovered_tool_count"] = len(tools)
            report["server_info"] = adapter.client.server_info.model_dump(exclude_none=True)
            examples = {tool.name: tool for tool in tools if tool.name in FREE}
            assert set(examples) == set(FREE), "Exact named free tools were not exposed"
            for name in FREE:
                # A ToolCall obtains the native LangChain ToolMessage + structured artifact.
                message = await examples[name].ainvoke({"name": name, "args": {}, "id": name, "type": "tool_call"})
                assert message.status == "success"
                fixture = message.artifact["structured_content"]
                verify_fixture(fixture)
                results[name] = {"content": message.content, "structuredContent": fixture}
            report["free_examples_verified"] = list(FREE)
            report["status"] = "PASS"
    except BaseException as exc:
        report["error"] = {"name": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["calls"] = calls
        (ROOT / "execution-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (ROOT / "free-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))

if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=90))
