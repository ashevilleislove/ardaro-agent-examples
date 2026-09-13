"""Offline boundary checks; no MCP connection or network call is made."""
import os
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

import unittest
from mcp.types import CallToolResult, TextContent, Tool
from free_fixture_adapter import FreeFixtureCrewAIAdapter


def definition(name="get_receipt_example", **overrides):
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    schema.update(overrides)
    return Tool(name=name, description="Fixed free synthetic fixture", inputSchema=schema)


class Boundaries(unittest.TestCase):
    def test_paid_tool_is_skipped_before_schema_mapping(self):
        adapter = FreeFixtureCrewAIAdapter()
        adapter.delegate.adapt = lambda *a: self.fail("Paid schema reached conversion")
        paid = definition("match_invoice", properties={"line_id": {"type": "string", "pattern": r"x(?![\s\S])"}})
        self.assertIsNone(adapter.adapt(lambda a: self.fail("Paid tool called"), paid))

    def test_empty_arguments_reach_actual_crewai_tool(self):
        calls = []
        def call(arguments):
            calls.append(arguments)
            return CallToolResult(content=[TextContent(type="text", text='{"synthetic_only":true}')])
        tool = FreeFixtureCrewAIAdapter().adapt(call, definition())
        self.assertEqual(tool.run(), '{"synthetic_only":true}')
        self.assertEqual(calls, [{}])

    def test_nonempty_arguments_never_reach_mcp(self):
        tool = FreeFixtureCrewAIAdapter().adapt(lambda a: self.fail("Unsafe arguments dispatched"), definition())
        with self.assertRaisesRegex(ValueError, "empty argument"):
            tool.run(customer_text="must not be sent")

    def test_dynamic_fixture_schema_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "argument schema changed"):
            FreeFixtureCrewAIAdapter().adapt(lambda a: None, definition(properties={"text": {"type": "string"}}))

    def test_open_argument_schema_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "argument schema changed"):
            FreeFixtureCrewAIAdapter().adapt(lambda a: None, definition(additionalProperties=True))

    def test_mcp_error_is_not_presented_as_success(self):
        def call(arguments):
            return CallToolResult(isError=True, content=[TextContent(type="text", text="error")])
        tool = FreeFixtureCrewAIAdapter().adapt(call, definition("get_invoice_matching_example"))
        with self.assertRaisesRegex(RuntimeError, "MCP tool error"):
            tool.run()


if __name__ == "__main__":
    unittest.main()
