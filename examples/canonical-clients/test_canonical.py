"""Offline canonical-schema and native-framework boundary tests."""
import os
os.environ.update(OTEL_SDK_DISABLED="true", CREWAI_DISABLE_TELEMETRY="true",
                  LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false", DO_NOT_TRACK="1")
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from canonical_mcp import CanonicalContract, ContractViolation, MCPResponseError, crewai_adapter, langchain_tools

ROOT = Path(__file__).parent / "fixtures"
DOCUMENT = json.loads((ROOT / "tools-list.json").read_text())
DEFINITIONS = DOCUMENT["result"]["tools"]
CASES = json.loads((ROOT / "semantic-cases.json").read_text())["cases"]
RESULTS = json.loads((ROOT / "free-results.json").read_text())


def deny_network(*args, **kwargs):
    raise AssertionError("Offline test attempted networking")


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = CanonicalContract(DOCUMENT)

    def test_fifty_four_canonical_cases_without_coercion(self):
        self.assertEqual(len(CASES), 54)
        for case in CASES:
            with self.subTest(name=case["name"], case=case["case"]):
                before = deepcopy(case["arguments"])
                if case["valid"]:
                    self.assertEqual(self.contract.validate(case["name"], "inputSchema", before), before)
                else:
                    with self.assertRaises(ContractViolation):
                        self.contract.validate(case["name"], "inputSchema", before)
                self.assertEqual(before, case["arguments"])

    def test_all_schema_definitions_preserved_and_ten_output_guards(self):
        self.assertEqual(list(self.contract.tools.values()), DEFINITIONS)
        output_count = 0
        for definition in DEFINITIONS:
            if "outputSchema" in definition:
                output_count += 1
                with self.assertRaises(ContractViolation):
                    self.contract.validate(definition["name"], "outputSchema", {})
        self.assertEqual(output_count, 10)

    def test_free_outputs_and_error_outcomes(self):
        for name, fixture in RESULTS.items():
            self.assertEqual(self.contract.finish(name, {"isError": False, "structuredContent": fixture}), fixture)
        with self.assertRaises(MCPResponseError):
            self.contract.finish("match_invoice", {"isError": True, "content": []})
        with self.assertRaises(ContractViolation):
            self.contract.finish("get_receipt_example", {"isError": False, "structuredContent": {}})

    def test_valid_paid_inputs_not_authorized_by_discovery(self):
        for case in CASES:
            if case["valid"] and self.contract.tools[case["name"]].get("_meta", {}).get("ardaro/serviceId"):
                with self.assertRaises(PermissionError):
                    self.contract.prepare(case["name"], case["arguments"])

    def test_malformed_duplicate_or_remote_reference_catalog_fails(self):
        with self.assertRaises(ValueError):
            CanonicalContract(DEFINITIONS + [DEFINITIONS[0]])
        changed = deepcopy(DEFINITIONS); del changed[0]["inputSchema"]["type"]
        with self.assertRaises(ValueError):
            CanonicalContract(changed)
        changed = deepcopy(DEFINITIONS)
        changed[1]["inputSchema"]["allOf"] = [{"$ref": "https://example.invalid/private-schema"}]
        remote = CanonicalContract(changed)
        with self.assertRaises(Exception):
            remote.validate(changed[1]["name"], "inputSchema", {})


@unittest.skipUnless(importlib.util.find_spec("crewai"), "CrewAI is not installed in this environment")
class NativeCrewAITests(unittest.TestCase):
    def test_full_catalog_native_and_structured_invocation_guards(self):
        with patch.object(socket.socket, "connect", deny_network), patch.object(socket, "create_connection", deny_network):
            from mcp.types import Tool, CallToolResult
            calls = []
            adapter = crewai_adapter(DOCUMENT)
            def callback(name):
                def call(arguments):
                    calls.append((name, arguments))
                    return CallToolResult(isError=False, structuredContent=RESULTS[name], content=[])
                return call
            native = {d["name"]: adapter.adapt(callback(d["name"]), Tool.model_validate(d)) for d in DEFINITIONS}
            self.assertEqual(len(native), 18)
            for definition in DEFINITIONS:
                tool = native[definition["name"]]
                self.assertEqual(tool.args_schema.model_json_schema(), definition["inputSchema"])
                if "outputSchema" in definition:
                    self.assertEqual(tool.result_schema.model_json_schema(), definition["outputSchema"])
                else:
                    self.assertIsNone(tool.result_schema)
                with self.assertRaises(ValueError):
                    tool.run(__unexpected=True)
                with self.assertRaises(ValueError):
                    tool.to_structured_tool().invoke({"__unexpected": True})
            for name, fixture in RESULTS.items():
                self.assertEqual(native[name].run(), fixture)
                self.assertEqual(native[name].to_structured_tool().invoke({}), fixture)
            for case in CASES:
                if not case["valid"]:
                    with self.assertRaises(ValueError):
                        native[case["name"]].run(**case["arguments"])
                    with self.assertRaises(ValueError):
                        native[case["name"]].to_structured_tool().invoke(case["arguments"])
            self.assertEqual(len(calls), 4)
            self.assertTrue(all(args == {} for _, args in calls))


@unittest.skipUnless(importlib.util.find_spec("langchain_core"), "LangChain is not installed in this environment")
class NativeLangChainTests(unittest.TestCase):
    def test_full_catalog_native_invocation_guards(self):
        async def check():
            calls = []
            async def call(name, args):
                calls.append((name, args))
                return {"isError": False, "structuredContent": RESULTS[name]}
            native = {t.name: t for t in langchain_tools(DOCUMENT, call)}
            self.assertEqual(len(native), 18)
            for definition in DEFINITIONS:
                tool = native[definition["name"]]
                self.assertEqual(tool.args_schema, definition["inputSchema"])
                self.assertEqual(tool.metadata["canonical_mcp_tool"], definition)
                with self.assertRaises(ValueError):
                    await tool.ainvoke({"__unexpected": True})
            for name, fixture in RESULTS.items():
                self.assertEqual(await native[name].ainvoke({}), fixture)
            for case in CASES:
                if not case["valid"]:
                    with self.assertRaises(ValueError):
                        await native[case["name"]].ainvoke(case["arguments"])
            self.assertEqual(len(calls), 2)
        # Windows asyncio creates an internal loopback socketpair at startup.
        # Initialize that loop before blocking every subsequent socket connect.
        with asyncio.Runner() as runner:
            with patch.object(socket.socket, "connect", deny_network), patch.object(socket, "create_connection", deny_network):
                runner.run(check())


if __name__ == "__main__":
    unittest.main()
