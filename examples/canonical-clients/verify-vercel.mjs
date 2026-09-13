// Live AI SDK construction of all 18 tools; invoke only two fixed free examples.
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {createMCPClient} from '@ai-sdk/mcp';
import {createCanonicalTools, ENDPOINT, FREE_EXAMPLES} from './canonical-vercel.mjs';
const output = process.argv[2];
if (!output) throw new Error('Provide a new output directory');
await mkdir(output, {recursive: false});
const expected = JSON.parse(await readFile(new URL('./fixtures/tools-list.json', import.meta.url), 'utf8')).result.tools;
const canonical = value => value === null || typeof value !== 'object' ? value : Array.isArray(value) ? value.map(canonical) : Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])]));
const digest = value => createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex');
const calls = [], results = {};
const nativeFetch = globalThis.fetch;
async function guardedFetch(input, init = {}) {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  assert.equal(url, ENDPOINT); assert.ok(calls.length < 20);
  const headers = new Headers(init.headers ?? (input instanceof Request ? input.headers : undefined));
  for (const key of headers.keys()) assert.ok(!/authorization|payment|api-key/i.test(key));
  const method = init.method ?? (input instanceof Request ? input.method : 'GET');
  let rpc;
  if (method === 'POST') {
    const body = typeof init.body === 'string' ? init.body : input instanceof Request ? await input.clone().text() : null;
    rpc = JSON.parse(body);
    assert.ok(['server/discover', 'initialize', 'notifications/initialized', 'tools/list', 'tools/call', 'ping'].includes(rpc.method));
    assert.ok(!('_meta' in (rpc.params ?? {})));
    if (rpc.method === 'tools/call') {
      assert.ok(FREE_EXAMPLES.includes(rpc.params.name)); assert.deepEqual(rpc.params.arguments ?? {}, {});
      assert.ok(Object.keys(rpc.params).every(k => ['name', 'arguments'].includes(k)));
      assert.ok(!calls.some(c => c.tool === rpc.params.name));
    }
  } else assert.ok(['GET', 'DELETE'].includes(method));
  const entry = {method, rpc_method: rpc?.method ?? null, tool: rpc?.method === 'tools/call' ? rpc.params.name : null};
  calls.push(entry);
  const response = await nativeFetch(input, {...init, redirect: 'error', signal: AbortSignal.any([...(init.signal ? [init.signal] : []), AbortSignal.timeout(20000)])});
  entry.http_status = response.status;
  if (response.ok && rpc?.method === 'tools/list') {
    const text = await response.clone().text(); assert.ok(Buffer.byteLength(text) <= 2097152);
    assert.deepEqual(JSON.parse(text).result.tools, expected);
  }
  return response;
}
let client;
const report = {status: 'FAIL', framework: 'vercel', started_at: new Date().toISOString(), endpoint: ENDPOINT,
  node: process.version, model_calls: 0, paid_tool_calls: 0, wallet_operations: 0,
  scope: '18 canonical native tool definitions; live execution of two fixed free examples only',
  schema_count: 18, declared_output_schema_count: 10, output_schema_absent_count: 8,
  adapter: 'explicit canonical JSON Schema/Ajv validation'};
try {
  client = await createMCPClient({transport: {type: 'http', url: ENDPOINT, fetch: guardedFetch}, maxRetries: 0});
  const definitions = await client.listTools(); assert.equal(definitions.tools.length, 18);
  const {tools} = createCanonicalTools(client, definitions);
  assert.equal(Object.keys(tools).length, 18);
  for (const definition of expected) {
    const native = tools[definition.name];
    assert.deepEqual(native.inputSchema.jsonSchema, definition.inputSchema);
    if (definition.outputSchema) assert.deepEqual(native.outputSchema.jsonSchema, definition.outputSchema);
    await assert.rejects(native.execute({__unexpected: true}, {toolCallId: 'offline-rejection', messages: []}));
  }
  const semanticCases = JSON.parse(await readFile(new URL('./fixtures/semantic-cases.json', import.meta.url), 'utf8')).cases;
  for (const item of semanticCases.filter(c => !c.valid)) {
    await assert.rejects(tools[item.name].execute(item.arguments, {toolCallId: 'offline-case', messages: []}));
  }
  for (const name of FREE_EXAMPLES) {
    const fixture = await tools[name].execute({}, {toolCallId: name, messages: []});
    assert.equal(fixture.synthetic_only, true);
    const response = fixture.expected_response ?? fixture.response;
    assert.equal(response.status, 'review_required');
    assert.equal(response.identities.analysis_result_identity, 'res_' + digest(response.result));
    results[name] = fixture;
  }
  Object.assign(report, {status: 'PASS_FULL_CATALOG_FREE_ONLY', server_info: client.serverInfo,
    protocol_version: client.initializeResult.protocolVersion, canonical_schemas_unchanged: true,
    canonical_tools_sha256: digest(expected), live_free_examples: FREE_EXAMPLES,
    native_invalid_input_rejections_before_transport: 18 + semanticCases.filter(c => !c.valid).length});
} catch (error) {
  report.error = {type: error.name, message: error.message}; process.exitCode = 1;
} finally {
  if (client) await client.close();
  Object.assign(report, {finished_at: new Date().toISOString(), calls});
  await writeFile(join(output, 'execution-report.json'), JSON.stringify(report, null, 2) + '\n');
  await writeFile(join(output, 'free-results.json'), JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(report));
}
