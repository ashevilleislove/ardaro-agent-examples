import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {canonicalContract, createCanonicalTools} from './canonical-vercel.mjs';
const read = async name => JSON.parse(await readFile(new URL(`./fixtures/${name}`, import.meta.url), 'utf8'));
const document = await read('tools-list.json');
const cases = (await read('semantic-cases.json')).cases;
const results = await read('free-results.json');

test('all 18 schemas and 54 exact semantic input cases survive without coercion', () => {
  const contract = canonicalContract(document);
  assert.equal(cases.length, 54);
  for (const definition of document.result.tools) {
    assert.deepEqual(contract.schemas[definition.name].inputSchema.jsonSchema, definition.inputSchema);
    if (definition.outputSchema) assert.deepEqual(contract.schemas[definition.name].outputSchema.jsonSchema, definition.outputSchema);
    else assert.equal(contract.schemas[definition.name].outputSchema, undefined);
  }
  for (const item of cases) {
    const before = structuredClone(item.arguments);
    if (item.valid) assert.deepEqual(contract.validate(item.name, 'inputSchema', item.arguments), item.arguments);
    else assert.throws(() => contract.validate(item.name, 'inputSchema', item.arguments));
    assert.deepEqual(item.arguments, before);
  }
});

test('ten output contracts reject empty objects; fixed fixtures validate', () => {
  const contract = canonicalContract(document);
  const declared = document.result.tools.filter(t => t.outputSchema);
  assert.equal(declared.length, 10);
  for (const t of declared) assert.throws(() => contract.validate(t.name, 'outputSchema', {}));
  for (const [name, value] of Object.entries(results)) assert.deepEqual(contract.validate(name, 'outputSchema', value), value);
});

test('valid paid arguments need separate call policy', () => {
  const contract = canonicalContract(document);
  for (const t of document.result.tools.filter(t => t._meta?.['ardaro/serviceId'])) {
    const item = cases.find(c => c.valid && c.name === t.name);
    assert.throws(() => contract.prepare(t.name, item.arguments), /explicit client call policy/);
  }
});

test('duplicate, malformed, nonfinite and unresolved reference data fail closed', () => {
  assert.throws(() => canonicalContract([...document.result.tools, document.result.tools[0]]));
  const changed = structuredClone(document); delete changed.result.tools[0].inputSchema.type;
  assert.throws(() => canonicalContract(changed));
  assert.throws(() => canonicalContract(document).validate('get_receipt_example', 'inputSchema', {value: NaN}));
  const remote = structuredClone(document); remote.result.tools[0].inputSchema.allOf = [{$ref: 'https://example.invalid/schema'}];
  assert.throws(() => canonicalContract(remote));
});

test('execution wrapper rejects invalid and disabled calls before a client callback', async () => {
  let calls = 0;
  // Pure adapter boundary only; native AI SDK construction is verified separately.
  const client = {toolsFromDefinitions(definitions, {schemas}) {
    return Object.fromEntries(definitions.tools.map(t => [t.name, {
      inputSchema: schemas[t.name].inputSchema,
      execute: async () => {calls++; return results[t.name];},
    }]));
  }};
  const {tools} = createCanonicalTools(client, document);
  for (const tool of Object.values(tools)) await assert.rejects(tool.execute({__unexpected: true}, {}));
  assert.equal(calls, 0);
  for (const name of Object.keys(results)) assert.deepEqual(await tools[name].execute({}, {}), results[name]);
  assert.equal(calls, 2);
});
