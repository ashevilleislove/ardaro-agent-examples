"""Explicit free-only CrewAI adapter using MCPAdapt's ToolAdapter extension.

This is an alternative to the stock MCPServerAdapter, not a patch to it.
Non-allowlisted tools are skipped before CrewAI converts their JSON Schemas.
"""
from contextlib import contextmanager
import json
from pathlib import Path

from crewai_tools.adapters.mcp_adapter import CrewAIToolAdapter
from mcpadapt.core import MCPAdapt, ToolAdapter

ENDPOINT = "https://agents.getardaro.com/mcp"
FREE_TOOLS = frozenset({"get_receipt_example", "get_invoice_matching_example"})


class FreeFixtureCrewAIAdapter(ToolAdapter):
    def __init__(self):
        self.delegate = CrewAIToolAdapter()
        self.discovered_names = []

    def adapt(self, func, mcp_tool):
        self.discovered_names.append(mcp_tool.name)
        if mcp_tool.name not in FREE_TOOLS:
            return None
        schema = mcp_tool.inputSchema
        if (
            schema.get("type") != "object"
            or schema.get("properties", {}) != {}
            or schema.get("required", []) != []
            or schema.get("additionalProperties") is not False
        ):
            raise RuntimeError("The public fixed-fixture argument schema changed")

        def call_empty_fixture(arguments):
            if arguments != {}:
                raise ValueError("Only an empty argument object is allowed")
            result = func({})
            if result.isError:
                raise RuntimeError("The free fixture returned an MCP tool error")
            return result

        return self.delegate.adapt(call_empty_fixture, mcp_tool)


@contextmanager
def free_fixture_tools():
    """Yield (two real CrewAI BaseTools, discovered names); never expose paid tools."""
    adapter = FreeFixtureCrewAIAdapter()
    config = json.loads(Path(__file__).with_name("crewai.connection.json").read_text(encoding="utf-8"))
    if config != {"url": ENDPOINT, "transport": "streamable-http"}:
        raise RuntimeError("Only the exact public MCP endpoint and transport are allowed")
    client = MCPAdapt(
        config,
        adapter,
        connect_timeout=40,
        client_session_timeout_seconds=10.0,
    )
    try:
        client.start()
        tools = [tool for tool in client.tools() if tool is not None]
        if len(tools) != 2 or {tool.name for tool in tools} != FREE_TOOLS:
            raise RuntimeError("The two fixed free tools were not discovered exactly once")
        yield tools, adapter.discovered_names
    finally:
        client.close()
