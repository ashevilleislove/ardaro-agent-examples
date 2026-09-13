// Explicit full-catalog AI SDK adapter. No connection is opened by this module.
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {jsonSchema} from '@ai-sdk/provider-utils';

export const ENDPOINT = 'https://agents.getardaro.com/mcp';
export const FREE_EXAMPLES = ['get_receipt_example', 'get_invoice_matching_example'];

function copyJson(value) {
  function check(item, depth = 0) {
    if (depth > 100) throw new Error('JSON nesting bound exceeded');
    if (item !== null && typeof item === 'object') {
      if (!Array.isArray(item) && ![Object.prototype, null].includes(Object.getPrototypeOf(item))) throw new Error('Only plain JSON values are supported');
      for (const value of Object.values(item)) check(value, depth + 1);
    }
  }
  check(value);
  const encoded = JSON.stringify(value, (_, item) => {
    if (['undefined', 'bigint', 'function', 'symbol'].includes(typeof item) ||
        (typeof item === 'number' && !Number.isFinite(item))) throw new Error('Non-JSON value');
    return item;
  });
  if (!encoded || Buffer.byteLength(encoded) > 2097152) throw new Error('JSON size bound exceeded');
  return JSON.parse(encoded);
}

export function canonicalContract(input, {allowedTools = FREE_EXAMPLES} = {}) {
  const data = copyJson(input);
  const result = Array.isArray(data) ? {tools: data} : data.result ?? data;
  if (data.error || 'nextCursor' in result || !Array.isArray(result.tools) ||
      result.tools.length < 1 || result.tools.length > 128) throw new Error('Invalid/incomplete catalog');
  const definitions = copyJson(result);
  const byName = new Map(), validators = new Map();
  // strict=false permits valid type-less union/conditional branches and MCP
  // annotations. It does not turn off JSON Schema instance validation.
  const ajv = new Ajv2020({strict: false, strictNumbers: true, allErrors: false,
    coerceTypes: false, useDefaults: false, removeAdditional: false, validateFormats: true});
  addFormats(ajv);
  for (const definition of definitions.tools) {
    const {name} = definition;
    if (typeof name !== 'string' || !name || byName.has(name)) throw new Error('Duplicate/missing name');
    byName.set(name, definition);
    for (const key of ['inputSchema', 'outputSchema']) {
      if (!(key in definition) && key === 'outputSchema') continue;
      const schema = definition[key];
      if (!schema || schema.type !== 'object') throw new Error('Explicit object root required');
      if (schema.$schema && schema.$schema !== 'https://json-schema.org/draft/2020-12/schema') throw new Error('Unsupported schema dialect');
      // Synchronous compile: unresolved remote refs fail; no fetch/loadSchema hook.
      validators.set(`${name}:${key}`, ajv.compile(copyJson(schema)));
    }
  }
  const allowed = new Set(allowedTools);
  if ([...allowed].some(name => !byName.has(name))) throw new Error('Unknown call-policy tool');
  function validate(name, key, value) {
    const clean = copyJson(value);
    if (!byName.has(name)) throw new Error('Unknown tool');
    const validator = validators.get(`${name}:${key}`);
    if (validator && !validator(clean)) throw new Error(`Canonical ${key} validation failed (${validator.errors?.[0]?.keyword})`);
    return clean;
  }
  const schemas = Object.fromEntries(definitions.tools.map(definition => {
    const make = key => jsonSchema(copyJson(definition[key]), {validate: async value => {
      try { return {success: true, value: validate(definition.name, key, value)}; }
      catch (error) { return {success: false, error}; }
    }});
    return [definition.name, {inputSchema: make('inputSchema'),
      ...('outputSchema' in definition ? {outputSchema: make('outputSchema')} : {})}];
  }));
  return {definitions, schemas, validate, prepare(name, args) {
    const clean = validate(name, 'inputSchema', args);
    if (!allowed.has(name)) throw new Error('Tool not enabled by explicit client call policy');
    return clean;
  }};
}

export function createCanonicalTools(client, definitions, options = {}) {
  const contract = canonicalContract(definitions, options);
  const native = client.toolsFromDefinitions(copyJson(contract.definitions), {schemas: contract.schemas});
  const tools = Object.fromEntries(Object.entries(native).map(([name, tool]) => [name, {
    ...tool,
    execute: async (arguments_, executionOptions) => {
      const result = await tool.execute(contract.prepare(name, arguments_), executionOptions);
      if (result?.isError === true) {
        const error = new Error('MCP tool returned an error; no successful outcome established');
        error.mcpResult = result;
        throw error;
      }
      const outputDeclared = Boolean(contract.schemas[name].outputSchema);
      if (outputDeclared) return contract.validate(name, 'outputSchema', result);
      return result?.structuredContent ?? result;
    },
  }]));
  return {tools, contract};
}
