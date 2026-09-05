import test from 'node:test';
import assert from 'node:assert/strict';
import { MCP_ENDPOINT, PAID_RESOURCE, createNoSpendFetch, runReceiptDemo } from '../src/receipt-demo.mjs';

function mockClient({ fixtureChange = {}, challengeChange = {}, offerChange = {}, tools } = {}) {
  const calls = [];
  const fixture = {
    synthetic_only: true, paid_processing_performed: false,
    request: { contract_version: 'ardaro.agent-receipt-intelligence.request.v1',
      input: { kind: 'text', text: 'SYNTHETIC TEST ONLY' }, existing_fingerprints: [] },
    ...fixtureChange
  };
  const challenge = { x402Version: 2, resource: { url: PAID_RESOURCE }, accepts: [
    { scheme: 'exact', network: 'eip155:8453', amount: '250000', ...offerChange }
  ], ...challengeChange };
  return {
    calls,
    listTools: async () => ({ tools: (tools ?? ['get_receipt_example', 'analyze_receipt']).map(name => ({ name })) }),
    callTool: async call => {
      calls.push(structuredClone(call));
      return call.name === 'get_receipt_example'
        ? { isError: false, structuredContent: fixture }
        : { isError: true, structuredContent: challenge, content: [{ type: 'text', text: JSON.stringify(challenge) }] };
    }
  };
}

test('happy path stops at the unpaid challenge and sends only synthetic arguments', async () => {
  const client = mockClient();
  const result = await runReceiptDemo(client);
  assert.equal(result.fundsSpent, 0);
  assert.equal(result.paidSettlement, 'not attempted');
  assert.equal(result.paymentChallenge.paymentSent, false);
  assert.deepEqual(client.calls, [
    { name: 'get_receipt_example', arguments: {} },
    { name: 'analyze_receipt', arguments: result.freeExample.request }
  ]);
});

test('missing tools fail before invocation', async () => {
  const client = mockClient({ tools: ['get_receipt_example'] });
  await assert.rejects(runReceiptDemo(client), /Required tool missing/);
  assert.equal(client.calls.length, 0);
});

for (const fixtureChange of [
  { synthetic_only: false }, { paid_processing_performed: true },
  { request: { _meta: { 'x402/payment': {} } } }
]) {
  test(`rejects an unsafe fixture: ${Object.keys(fixtureChange)[0]}`, async () => {
    const client = mockClient({ fixtureChange });
    await assert.rejects(runReceiptDemo(client));
    assert.equal(client.calls.length, 1);
  });
}

for (const offerChange of [
  { amount: '250001' }, { amount: 250000 }, { network: 'eip155:84532' }, { scheme: 'other' }
]) {
  test(`rejects an unexpected payment offer: ${JSON.stringify(offerChange)}`, async () => {
    await assert.rejects(runReceiptDemo(mockClient({ offerChange })));
  });
}

test('rejects a different signed resource', async () => {
  await assert.rejects(runReceiptDemo(mockClient({ challengeChange: { resource: { url: MCP_ENDPOINT } } })), /Unexpected payable resource/);
});

test('guard fixes destination, disables redirects and credentials', async () => {
  let captured;
  const safeFetch = createNoSpendFetch(async (url, init) => { captured = { url, init }; return new Response('{}'); });
  await safeFetch(MCP_ENDPOINT, { method: 'POST', body: JSON.stringify({ jsonrpc: '2.0', method: 'tools/list', id: 1 }), credentials: 'include', redirect: 'follow' });
  assert.equal(captured.url, MCP_ENDPOINT);
  assert.equal(captured.init.credentials, 'omit');
  assert.equal(captured.init.redirect, 'error');
  assert.ok(captured.init.signal instanceof AbortSignal);
});

for (const url of ['https://example.com/mcp', `${MCP_ENDPOINT}?key=secret`, 'http://agents.getardaro.com/mcp']) {
  test(`guard rejects noncanonical destination ${url}`, async () => {
    await assert.rejects(createNoSpendFetch(() => assert.fail('Must not fetch'))(url));
  });
}

for (const header of ['Authorization', 'Cookie', 'PAYMENT-SIGNATURE', 'X-PAYMENT']) {
  test(`guard rejects ${header} before sending`, async () => {
    await assert.rejects(createNoSpendFetch(() => assert.fail('Must not fetch'))(MCP_ENDPOINT, { headers: { [header]: 'never-sent' } }), /Header is not allowed/);
  });
}

test('guard rejects a payment payload before sending', async () => {
  await assert.rejects(createNoSpendFetch(() => assert.fail('Must not fetch'))(MCP_ENDPOINT, {
    method: 'POST', body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: {
      name: 'analyze_receipt', arguments: {}, _meta: { 'x402/payment': {} }
    } })
  }), /must not send payment/);
});

test('guard allows the SDK optional GET without a body', async () => {
  let called = false;
  await createNoSpendFetch(async () => { called = true; return new Response(null, { status: 405 }); })(new URL(MCP_ENDPOINT));
  assert.equal(called, true);
});

test('guard rejects unrecognized protocol methods', async () => {
  await assert.rejects(createNoSpendFetch(() => assert.fail('Must not fetch'))(MCP_ENDPOINT, {
    method: 'POST', body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'payments/send' })
  }), /Unexpected MCP method/);
});
