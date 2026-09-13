"""Run CrewAI's real MCP adapter against two public fixed fixtures only.

No Agent, Crew, model, wallet or buyer is instantiated. All outgoing HTTP and
JSON-RPC are checked before dispatch; model credentials are removed from this
process. Dependency installation is a separate step, outside this network gate.
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import hashlib
import importlib.metadata as metadata
import ipaddress
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time

ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://agents.getardaro.com/mcp"
FREE_TOOLS = ("get_receipt_example", "get_invoice_matching_example")
MODE = sys.argv[1] if len(sys.argv) == 2 else "allowlisted"
if MODE not in {"stock", "allowlisted"}:
    raise SystemExit("Usage: verify_free_adapter.py [stock|allowlisted]")
report = {
    "status": "RUNNING",
    "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "endpoint": ENDPOINT,
    "framework": "CrewAI MCPServerAdapter" if MODE == "stock" else "CrewAI via explicit free-only MCPAdapt ToolAdapter",
    "mode": MODE,
    "python": platform.python_version(),
    "versions": {},
    "requests": [],
    "results": {},
    "spend_usdc": "0.00",
    "model_calls": 0,
    "wallet_calls": 0,
    "paid_tool_calls": 0,
    "customer_input": False,
    "request_budget": 8,
    "scope": "Live discovery and direct execution of the adapter-mapped free fixed fixtures; no Crew/LLM execution or paid MCP execution.",
}

# Prevent imported packages from locating unrelated API credentials.
for key in tuple(os.environ):
    if any(marker in key.upper() for marker in ("API_KEY", "API_TOKEN", "ACCESS_TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY")):
        del os.environ[key]
os.environ.update({
    "OTEL_SDK_DISABLED": "true",
    "CREWAI_TELEMETRY": "false",
    "CREWAI_DISABLE_TELEMETRY": "true",
    "DO_NOT_TRACK": "1",
    "ANONYMIZED_TELEMETRY": "false",
})

# Permit the MCP host and local event-loop plumbing, but no other remote socket.
original_getaddrinfo = socket.getaddrinfo
addresses = {
    row[4][0]
    for row in original_getaddrinfo("agents.getardaro.com", 443, type=socket.SOCK_STREAM)
}
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex


def check_address(address):
    if not isinstance(address, tuple):
        raise RuntimeError("Non-TCP network address blocked")
    host, port = address[:2]
    try:
        if ipaddress.ip_address(host).is_loopback:
            return  # Windows asyncio socketpair plumbing.
    except ValueError:
        pass
    if host not in addresses or port != 443:
        raise RuntimeError("Remote connection outside MCP allowlist blocked")


def gated_connect(sock, address):
    check_address(address)
    return original_connect(sock, address)


def gated_connect_ex(sock, address):
    check_address(address)
    return original_connect_ex(sock, address)


def gated_getaddrinfo(host, port, *args, **kwargs):
    decoded = host.decode() if isinstance(host, bytes) else host
    if decoded not in {"agents.getardaro.com", "127.0.0.1", "::1", "localhost", None} and decoded not in addresses:
        raise RuntimeError("DNS lookup outside MCP allowlist blocked")
    return original_getaddrinfo(host, port, *args, **kwargs)


socket.socket.connect = gated_connect
socket.socket.connect_ex = gated_connect_ex
socket.getaddrinfo = gated_getaddrinfo

import httpx  # noqa: E402


def check_http(request):
    if len(report["requests"]) >= report["request_budget"]:
        raise RuntimeError("Bounded MCP request budget exhausted")
    if str(request.url) != ENDPOINT or request.method not in {"POST", "GET", "DELETE"}:
        raise RuntimeError("HTTP endpoint outside exact MCP allowlist blocked")
    if any(name in request.headers for name in ("authorization", "payment-signature", "x-payment", "cookie")):
        raise RuntimeError("Credential or payment header blocked")
    event = {"http_method": request.method, "url": str(request.url)}
    if request.method == "POST":
        payload = json.loads(request.content)
        if not isinstance(payload, dict):
            raise RuntimeError("JSON-RPC batch blocked")
        reject_payment_metadata(payload)
        method = payload.get("method")
        if method not in {"initialize", "notifications/initialized", "tools/list", "tools/call"}:
            raise RuntimeError("JSON-RPC method blocked")
        event["rpc_method"] = method
        event["params"] = payload.get("params", {})
        if method == "tools/call":
            params = payload.get("params", {})
            if params.get("name") not in FREE_TOOLS or params.get("arguments") != {}:
                raise RuntimeError("Only empty-argument fixed fixtures are authorized")
            if any(r.get("rpc_method") == "tools/call" and r.get("params", {}).get("name") == params["name"] for r in report["requests"]):
                raise RuntimeError("Repeated fixture call blocked")
        elif sum(r.get("rpc_method") == method for r in report["requests"]) >= (2 if method == "tools/list" else 1):
            raise RuntimeError("Repeated discovery request blocked")
    report["requests"].append(event)
    return event


def reject_payment_metadata(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"_meta", "payment", "payment-signature", "x-payment", "authorization", "payer_signature", "paymentrequired", "paymentpayload"}:
                raise RuntimeError("Payment or opaque metadata payload blocked")
            reject_payment_metadata(child)
    elif isinstance(value, list):
        for child in value:
            reject_payment_metadata(child)


original_async_send = httpx.AsyncClient.send
original_sync_send = httpx.Client.send


async def gated_async_send(client, request, **kwargs):
    event = check_http(request)
    kwargs["follow_redirects"] = False
    response = await original_async_send(client, request, **kwargs)
    event["http_status"] = response.status_code
    if 300 <= response.status_code < 400:
        await response.aclose()
        raise RuntimeError("Redirect blocked")
    if "application/json" in response.headers.get("content-type", ""):
        await response.aread()
        if event.get("rpc_method") == "initialize":
            body = response.json()
            report["server_info"] = body.get("result", {}).get("serverInfo")
            report["protocol_version"] = body.get("result", {}).get("protocolVersion")
    return response


def gated_sync_send(client, request, **kwargs):
    check_http(request)
    # MCP uses AsyncClient; no sync HTTP is required for this bounded check.
    raise RuntimeError("Unexpected synchronous HTTP blocked")


httpx.AsyncClient.send = gated_async_send
httpx.Client.send = gated_sync_send


def main():
    from crewai_tools import MCPServerAdapter

    @contextmanager
    def connection():
        if MODE == "stock":
            with MCPServerAdapter(config, connect_timeout=40) as tools:
                yield tools
        else:
            from free_fixture_adapter import free_fixture_tools
            with free_fixture_tools() as (tools, discovered):
                report["raw_discovered_tool_names"] = sorted(discovered)
                yield tools

    for package in ("crewai", "crewai-tools", "mcp", "mcpadapt", "httpx", "pydantic"):
        report["versions"][package] = metadata.version(package)
    config = {"url": ENDPOINT, "transport": "streamable-http"}
    began = time.monotonic()
    with connection() as tools:
        mapped = {tool.name: tool for tool in tools}
        report["discovered_tool_names"] = sorted(mapped)
        assert set(FREE_TOOLS).issubset(mapped), "Required free tools missing"
        for name in FREE_TOOLS:
            result = mapped[name].run()
            assert isinstance(result, str), "Adapter result must be JSON text"
            fixture = json.loads(result)
            reject_payment_metadata(fixture)
            assert fixture.get("synthetic_only") is True, "Not a fixed synthetic fixture"
            if "paid_processing_performed" in fixture:
                assert fixture["paid_processing_performed"] is False
            fixture_path = ROOT / f"{name}.result.json"
            fixture_path.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
            report["results"][name] = {
                "status": "PASS",
                "arguments": {},
                "adapter_output_type": type(result).__name__,
                "synthetic_only": True,
                "fixture_file": fixture_path.name,
                "sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            }
    calls = [r for r in report["requests"] if r.get("rpc_method") == "tools/call"]
    assert [r["params"]["name"] for r in calls] == list(FREE_TOOLS)
    report["elapsed_seconds"] = round(time.monotonic() - began, 3)
    report["status"] = "PASS"


try:
    main()
except Exception as exc:
    report["status"] = "FAIL"
    report["error"] = {"type": type(exc).__name__, "message": str(exc)[:2000]}
finally:
    report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    filename = "verification.json" if MODE == "stock" else "verification-allowlisted.json"
    (ROOT / filename).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
sys.exit(0 if report["status"] == "PASS" else 1)
