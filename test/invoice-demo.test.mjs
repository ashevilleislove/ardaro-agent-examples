import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInvoiceDemo, INVOICE_RESOURCE } from '../src/invoice-demo.mjs';
import { createNoSpendFetch, MCP_ENDPOINT } from '../src/receipt-demo.mjs';

const savedFixture = JSON.parse(readFileSync(new URL('./fixtures/invoice-example.json', import.meta.url)));
const savedStatus = JSON.parse(readFileSync(new URL('./fixtures/invoice-status.json', import.meta.url)));
function mockClient(change = () => {}) {
  const fixture = structuredClone(savedFixture);
  const status = structuredClone(savedStatus);
  const challenge = { x402Version: 2, resource: { url: INVOICE_RESOURCE }, accepts: [{ scheme: 'exact',
    network: 'eip155:8453', amount: '500000', asset: '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913', payTo: '0x' + '1'.repeat(40) }] };
  change({ fixture, status, challenge });
  const calls = [];
  return { calls,
    listTools: async () => ({ tools: ['get_invoice_matching_service_status', 'get_invoice_matching_example', 'match_invoice'].map(name => ({ name })) }),
    callTool: async call => {
      calls.push(structuredClone(call));
      if (call.name === 'get_invoice_matching_service_status') return { structuredContent: status };
      if (call.name === 'get_invoice_matching_example') return { structuredContent: fixture };
      return { isError: true, structuredContent: challenge, content: [{ type: 'text', text: JSON.stringify(challenge) }] };
    }
  };
}

test('invoice proof keeps even a no-discrepancies result in human review and never pays', async () => {
  const client = mockClient();
  const result = await runInvoiceDemo(client);
  assert.equal(result.fundsSpent, 0);
  assert.equal(result.paidSettlement, 'not attempted');
  assert.equal(result.reviewHandoff.disposition, 'human_review_required');
  assert.equal(result.reviewHandoff.summary.outcome, 'no_discrepancies');
  assert.equal(result.paymentChallenge.recipientIndependentlyVerified, false);
  assert.deepEqual(client.calls, [
    { name: 'get_invoice_matching_service_status', arguments: {} },
    { name: 'get_invoice_matching_example', arguments: {} },
    { name: 'match_invoice', arguments: savedFixture.request }
  ]);
});

test('closed service prevents subsequent calls', async () => {
  const client = mockClient(({ status }) => { status.ready = false; });
  await assert.rejects(runInvoiceDemo(client), /not currently ready/);
  assert.equal(client.calls.length, 1);
});

for (const [name, change] of [
  ['non-synthetic example', ({ fixture }) => { fixture.synthetic_only = false; }],
  ['embedded payment', ({ fixture }) => { fixture.request._meta = { 'x402/payment': {} }; }],
  ['altered result', ({ fixture }) => { fixture.response.result.summary.discrepancy_count = 7; }],
  ['missing review requirement', ({ fixture }) => { fixture.response.result.summary.human_review_required = false; }],
]) {
  test(`rejects ${name} before requesting a quote`, async () => {
    const client = mockClient(change);
    await assert.rejects(runInvoiceDemo(client));
    assert.equal(client.calls.length, 2);
  });
}

for (const [name, change] of [
  ['price', c => { c.accepts[0].amount = '500001'; }],
  ['network', c => { c.accepts[0].network = 'eip155:84532'; }],
  ['asset', c => { c.accepts[0].asset = '0x' + '2'.repeat(40); }],
  ['resource', c => { c.resource.url = MCP_ENDPOINT; }],
  ['multiple options', c => { c.accepts.push(c.accepts[0]); }],
]) {
  test(`rejects unexpected invoice ${name} without retrying`, async () => {
    const client = mockClient(({ challenge }) => change(challenge));
    await assert.rejects(runInvoiceDemo(client));
    assert.equal(client.calls.length, 3);
  });
}

test('invoice transport refuses signed metadata and arbitrary free-tool arguments before network access', async () => {
  const guarded = createNoSpendFetch(() => assert.fail('Must not fetch'));
  for (const params of [
    { name: 'match_invoice', arguments: savedFixture.request, _meta: { 'x402/payment': {} } },
    { name: 'get_invoice_matching_example', arguments: { invoice: {} } },
    { name: 'unknown_tool', arguments: {} }
  ]) {
    await assert.rejects(guarded(MCP_ENDPOINT, { method: 'POST', body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params }) }));
  }
});
