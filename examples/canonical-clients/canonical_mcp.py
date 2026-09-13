"""Explicit canonical-JSON-Schema adapters; import opens no connection.

Draft 2020-12 validation replaces schema-to-Pydantic conversion, not the schema.
Only the two fixed examples are callable by default. Extending the call allowlist
is a separate client policy decision; this module never signs or pays.
"""
from copy import deepcopy
import inspect
import json
import math

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import NoSuchResource

ENDPOINT = "https://agents.getardaro.com/mcp"
FREE_EXAMPLES = frozenset({"get_receipt_example", "get_invoice_matching_example"})


def _no_remote_reference(uri):
    raise NoSuchResource(ref=uri)


def _never_cache(*args):
    return False


def _json(value):
    def check(item, depth=0):
        if depth > 100:
            raise ValueError("JSON nesting bound exceeded")
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check(child, depth + 1)
        elif type(item) is list:
            for child in item:
                check(child, depth + 1)
        elif type(item) is float:
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
        elif item is not None and type(item) not in (str, int, bool):
            raise ValueError("Only JSON values are supported; no coercion")
    check(value)
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > 2_097_152:
        raise ValueError("Contract/value exceeds 2 MiB bound")
    return json.loads(encoded)


class ContractViolation(ValueError):
    """No input values are included in validation error messages."""


class MCPResponseError(RuntimeError):
    def __init__(self, result):
        super().__init__("MCP tool returned an error; no successful outcome established")
        self.result = result


class CanonicalContract:
    def __init__(self, tools, *, allowed_tools=FREE_EXAMPLES):
        if isinstance(tools, dict):
            if "error" in tools:
                raise ValueError("RPC error is not a tool catalog")
            tools = tools.get("result", tools)
            if "nextCursor" in tools:
                raise ValueError("Assemble all tool pages before constructing adapter")
            tools = tools.get("tools")
        tools = _json(tools)
        if not isinstance(tools, list) or not 1 <= len(tools) <= 128:
            raise ValueError("Expected a bounded, nonempty tools list")
        self.tools = {}
        self.validators = {}
        for tool in tools:
            name = tool.get("name")
            if not isinstance(name, str) or not name or name in self.tools:
                raise ValueError("Missing or duplicate tool name")
            for kind in ("inputSchema", "outputSchema"):
                if kind == "outputSchema" and kind not in tool:
                    continue
                schema = tool.get(kind)
                if not isinstance(schema, dict) or schema.get("type") != "object":
                    raise ValueError("MCP root schemas require explicit object type")
                if schema.get("$schema", "https://json-schema.org/draft/2020-12/schema") != "https://json-schema.org/draft/2020-12/schema":
                    raise ValueError("Revalidate unsupported JSON Schema dialect")
                Draft202012Validator.check_schema(schema)
                self.validators[name, kind] = Draft202012Validator(
                    deepcopy(schema), format_checker=FormatChecker(),
                    registry=Registry(retrieve=_no_remote_reference))
            self.tools[name] = tool
        self.allowed_tools = frozenset(allowed_tools)
        if not self.allowed_tools.issubset(self.tools):
            raise ValueError("Call policy names tools absent from this catalog")

    def validate(self, name, kind, value):
        if name not in self.tools:
            raise ContractViolation("Unknown tool")
        value = _json(value)
        validator = self.validators.get((name, kind))
        if validator is not None:
            error = next(validator.iter_errors(value), None)
            if error is not None:
                raise ContractViolation(f"Canonical {kind} validation failed ({error.validator})")
        return value

    def prepare(self, name, arguments):
        # Validate before policy: malformed paid inputs never reach any callback.
        arguments = self.validate(name, "inputSchema", arguments)
        if name not in self.allowed_tools:
            raise PermissionError("Tool not enabled by explicit client call policy")
        return arguments

    def finish(self, name, result):
        def field(camel, snake=None):
            if isinstance(result, dict):
                return result.get(camel, result.get(snake))
            return getattr(result, camel, getattr(result, snake or camel, None))
        is_error = field("isError", "is_error")
        if type(is_error) is not bool:
            raise ContractViolation("MCP result lacks explicit error state")
        structured = field("structuredContent", "structured_content")
        if structured is None:
            content = field("content")
            if isinstance(content, list) and len(content) == 1:
                text = content[0].get("text") if isinstance(content[0], dict) else getattr(content[0], "text", None)
                if isinstance(text, str):
                    try:
                        structured = json.loads(text)
                    except json.JSONDecodeError:
                        pass
        # Preserve error outcomes separately; never turn an MCP error into success.
        if is_error:
            raise MCPResponseError(result)
        if (name, "outputSchema") in self.validators and structured is None:
            raise ContractViolation("MCP result lacks required structured output")
        if structured is not None:
            return self.validate(name, "outputSchema", structured)
        # Tools with no declared outputSchema remain explicitly unvalidated here.
        content = field("content")
        return [part if isinstance(part, dict) else part.model_dump(exclude_none=True)
                for part in content or []]


def _canonical_args_model(schema, validate):
    from pydantic import BaseModel, ConfigDict, model_validator

    class CanonicalArguments(BaseModel):
        model_config = ConfigDict(extra="allow", strict=True)

        @model_validator(mode="before")
        @classmethod
        def validate_json_schema(cls, value):
            return validate(value)

        @classmethod
        def __get_pydantic_json_schema__(cls, core_schema, handler):
            return deepcopy(schema)

    return CanonicalArguments


def crewai_adapter(tools, *, allowed_tools=FREE_EXAMPLES):
    """Return native MCPAdapt ToolAdapter; caller owns lifecycle/transport.

    All definitions are represented. `allowed_tools` is independent of discovery.
    No MCPServerAdapter or schema conversion helper is patched.
    """
    from crewai.tools import BaseTool
    from mcpadapt.core import ToolAdapter
    from pydantic import BaseModel
    contract = CanonicalContract(tools, allowed_tools=allowed_tools)

    class Adapter(ToolAdapter):
        canonical_contract = contract

        def adapt(self, func, mcp_tool):
            name = mcp_tool.name
            expected = contract.tools.get(name)
            actual = mcp_tool.model_dump(by_alias=True, exclude_none=True)
            if expected is None:
                raise ContractViolation("Unexpected discovered tool")
            for key in ("inputSchema", "outputSchema", "annotations", "_meta"):
                if json.dumps(actual.get(key), sort_keys=True) != json.dumps(expected.get(key), sort_keys=True):
                    raise ContractViolation("Live tool contract changed; recreate adapter")
            arguments_model = _canonical_args_model(expected["inputSchema"],
                lambda value: contract.validate(name, "inputSchema", value))

            class NativeTool(BaseTool):
                args_schema: type[BaseModel] = arguments_model

                def _run(self, **arguments):
                    result = func(contract.prepare(name, arguments))
                    if inspect.isawaitable(result):
                        raise TypeError("CrewAI synchronous callback returned an awaitable")
                    return contract.finish(name, result)

                def _generate_description(self):
                    # Include full canonical schema, including $defs and unions.
                    self.description = expected.get("description", "") + "\nCanonical input schema: " + json.dumps(expected["inputSchema"])

            native = NativeTool(name=name, description=expected.get("description", ""),
                                cache_function=_never_cache)
            # Preserve absent output schemas rather than inventing a contract.
            if "outputSchema" in expected:
                native.result_schema = _canonical_args_model(expected["outputSchema"],
                    lambda value: contract.validate(name, "outputSchema", value))
            return native

    return Adapter()


def langchain_tools(tools, call_tool, *, allowed_tools=FREE_EXAMPLES):
    """Return native StructuredTools using unchanged JSON-schema dictionaries.

    call_tool(name, arguments) must be async and return an MCP result. Validation
    occurs in the wrapper because LangChain's dictionary args_schema does not
    itself validate instances in the inspected version.
    """
    from langchain_core.tools import StructuredTool
    contract = CanonicalContract(tools, allowed_tools=allowed_tools)
    mapped = []
    for name, definition in contract.tools.items():
        def make_callback(tool_name):
            async def invoke(**arguments):
                result = await call_tool(tool_name, contract.prepare(tool_name, arguments))
                return contract.finish(tool_name, result)
            return invoke
        mapped.append(StructuredTool(name=name, description=definition.get("description", ""),
            args_schema=deepcopy(definition["inputSchema"]), coroutine=make_callback(name),
            metadata={"mcp_endpoint": ENDPOINT, "canonical_mcp_tool": deepcopy(definition),
                      "schema_validator": "jsonschema Draft202012Validator"}))
    return mapped
