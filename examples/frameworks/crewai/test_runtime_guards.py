"""Exercise the exact guard functions without importing the network harness."""
import ast
import json
from pathlib import Path
import unittest
import httpx


class RuntimeGuards(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name("verify_free_adapter.py").read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"check_http", "reject_payment_metadata"}]
        self.state = {"requests": [], "request_budget": 8}
        self.namespace = {
            "report": self.state,
            "ENDPOINT": "https://agents.getardaro.com/mcp",
            "FREE_TOOLS": ("get_receipt_example", "get_invoice_matching_example"),
            "json": json,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), "exact_runtime_guards", "exec"), self.namespace)

    def request(self, method="tools/call", params=None, **kwargs):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params if params is not None else {"name": "get_receipt_example", "arguments": {}}}
        return httpx.Request("POST", "https://agents.getardaro.com/mcp", json=payload, **kwargs)

    def test_eight_request_budget(self):
        self.state["requests"] = [{}] * 8
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            self.namespace["check_http"](self.request())

    def test_paid_tool_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "fixed fixtures"):
            self.namespace["check_http"](self.request(params={"name": "match_invoice", "arguments": {}}))

    def test_each_fixture_called_at_most_once(self):
        self.namespace["check_http"](self.request())
        with self.assertRaisesRegex(RuntimeError, "Repeated fixture"):
            self.namespace["check_http"](self.request())

    def test_discovery_is_bounded(self):
        for _ in range(2):
            self.namespace["check_http"](self.request("tools/list", {}))
        with self.assertRaisesRegex(RuntimeError, "Repeated discovery"):
            self.namespace["check_http"](self.request("tools/list", {}))

    def test_nested_metadata_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "metadata payload"):
            self.namespace["check_http"](self.request(params={"name": "get_receipt_example", "arguments": {}, "_meta": {}}))

    def test_payment_and_authorization_headers_rejected(self):
        for header in ("authorization", "payment-signature", "x-payment", "cookie"):
            with self.subTest(header=header), self.assertRaisesRegex(RuntimeError, "header blocked"):
                self.namespace["check_http"](self.request(headers={header: "synthetic-placeholder"}))

    def test_payment_body_rejected(self):
        for key in ("payment", "paymentPayload", "paymentRequired", "payer_signature"):
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "metadata payload"):
                self.namespace["reject_payment_metadata"]({"nested": [{key: {}}]})


if __name__ == "__main__":
    unittest.main()
