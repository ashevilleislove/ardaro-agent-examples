import assert from 'node:assert/strict';

export const MCP_ENDPOINT = 'https://agents.getardaro.com/mcp';
export const PAID_RESOURCE = 'https://agents.getardaro.com/v1/receipt-intelligence/analyze';
const allowedHeaders = new Set(['accept', 'content-type', 'mcp-protocol-version', 'mcp-session-id']);
const allowedMethods = new Set(['initialize', 'notifications/initialized', 'tools/list', 'tools/call']);

function rejectPaymentMetadata(value) {
  if (value === null || typeof value !== 'object') return;
  for (const [key, item] of Object.entries(value)) {
    assert.ok(!['_meta', 'signature', 'authorization', 'privateKey'].includes(key),
      'This demo must not send payment metadata or signing material.');
    rejectPaymentMetadata(item);
  }
}

// This is intentionally NOT a paying HTTP client. Its only destination is the
// public MCP endpoint; it rejects credentials, payment metadata and redirects.
export function createNoSpendFetch(fetchImpl = globalThis.fetch) {
  return async (input, init = {}) => {
    assert.ok(typeof input === 'string' || input instanceof URL, 'Expected a URL, not a Request.');
    assert.equal(new URL(input).href, MCP_ENDPOINT, 'The demo only calls the public Ardaro MCP endpoint.');
    const headers = new Headers(init.headers);
    for (const name of headers.keys()) {
      assert.ok(allowedHeaders.has(name), `Header is not allowed in the no-spend demo: ${name}`);
    }
    const method = (init.method ?? 'GET').toUpperCase();
    assert.ok(['GET', 'POST'].includes(method), 'Unexpected HTTP method.');
    if (method === 'POST') {
      assert.equal(typeof init.body, 'string', 'Expected a JSON message.');
      const message = JSON.parse(init.body);
      assert.ok(!Array.isArray(message), 'Batch requests are not part of this demo.');
      assert.equal(message.jsonrpc, '2.0');
      assert.ok(allowedMethods.has(message.method), 'Unexpected MCP method.');
      rejectPaymentMetadata(message);
      if (message.method === 'tools/call') {
        assert.ok(['get_receipt_example', 'analyze_receipt'].includes(message.params?.name), 'Unexpected tool.');
      }
    } else {
      assert.equal(init.body, undefined, 'GET must have no body.');
    }
    const timeout = AbortSignal.timeout(20_000);
    return fetchImpl(MCP_ENDPOINT, {
      ...init, headers, redirect: 'error', credentials: 'omit',
      signal: init.signal ? AbortSignal.any([init.signal, timeout]) : timeout
    });
  };
}

export async function runReceiptDemo(client) {
  const listing = await client.listTools();
  const names = listing.tools.map(tool => tool.name);
  for (const required of ['get_receipt_example', 'analyze_receipt']) {
    assert.ok(names.includes(required), `Required tool missing: ${required}`);
  }

  const example = await client.callTool({ name: 'get_receipt_example', arguments: {} });
  assert.notEqual(example.isError, true, 'The free example failed.');
  const fixture = example.structuredContent;
  assert.equal(fixture?.synthetic_only, true, 'Expected synthetic data only.');
  assert.equal(fixture.paid_processing_performed, false, 'Expected a free fixture, not paid processing.');
  assert.ok(fixture.request && typeof fixture.request === 'object' && !Array.isArray(fixture.request));
  rejectPaymentMetadata(fixture.request);

  // Reuse only the public synthetic fixture. There is no user-data input path,
  // wallet, payment payload or automatic retry with a payment authorization.
  const unpaid = await client.callTool({ name: 'analyze_receipt', arguments: fixture.request });
  assert.equal(unpaid.isError, true, 'Expected a payment-required tool result, not paid analysis.');
  const challenge = unpaid.structuredContent;
  assert.equal(challenge?.x402Version, 2, 'Expected an x402 v2 challenge.');
  assert.equal(challenge.resource?.url, PAID_RESOURCE, 'Unexpected payable resource.');
  assert.ok(Array.isArray(challenge.accepts) && challenge.accepts.length > 0);
  for (const offer of challenge.accepts) {
    assert.equal(offer.scheme, 'exact');
    assert.equal(offer.network, 'eip155:8453');
    assert.equal(offer.amount, '250000');
  }
  const text = unpaid.content?.find(item => item.type === 'text');
  assert.ok(text, 'The challenge must also have a text representation.');
  assert.deepEqual(JSON.parse(text.text), challenge);

  return {
    endpoint: MCP_ENDPOINT,
    tools: names,
    freeExample: fixture,
    paymentChallenge: {
      version: challenge.x402Version,
      resource: challenge.resource.url,
      scheme: challenge.accepts[0].scheme,
      network: challenge.accepts[0].network,
      amountAtomic: challenge.accepts[0].amount,
      price: '0.25 USDC',
      paymentSent: false
    },
    checks: { discovery: 'passed', syntheticExample: 'passed', unpaidChallenge: 'passed' },
    paidSettlement: 'not attempted',
    fundsSpent: 0
  };
}
