import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { MCP_ENDPOINT, rejectPaymentMetadata } from './receipt-demo.mjs';

export const INVOICE_RESOURCE = 'https://agents.getardaro.com/v1/invoice-matching/analyze';
const USDC = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913';

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}

export async function runInvoiceDemo(client) {
  const listing = await client.listTools();
  assert.ok(!listing.nextCursor, 'Expected one complete tool page.');
  const names = listing.tools.map(tool => tool.name);
  for (const required of ['get_invoice_matching_service_status', 'get_invoice_matching_example', 'match_invoice']) {
    assert.ok(names.includes(required), `Required tool missing: ${required}`);
  }
  const statusCall = await client.callTool({ name: 'get_invoice_matching_service_status', arguments: {} });
  assert.notEqual(statusCall.isError, true, 'The free readiness check failed.');
  const status = statusCall.structuredContent;
  assert.equal(status?.service_id, 'ardaro.invoice_matching');
  assert.equal(status.ready, true, 'Service is not currently ready.');
  assert.equal(status.price?.amount_atomic, '500000', 'Published invoice price changed.');
  assert.equal(status.price.currency, 'USDC');
  assert.equal(status.price.network, 'eip155:8453');
  assert.equal(status.policy?.human_review_required, true);
  assert.equal(status.policy.financial_mutation_supported, false);
  assert.equal(status.policy.ardaro_saas_tenant_access, false);

  const example = await client.callTool({ name: 'get_invoice_matching_example', arguments: {} });
  assert.notEqual(example.isError, true, 'The free example failed.');
  const fixture = example.structuredContent;
  assert.equal(fixture?.synthetic_only, true, 'Expected the fixed synthetic example.');
  assert.equal(fixture.policy?.payment_required, false);
  assert.equal(fixture.policy.human_review_required, true);
  assert.equal(fixture.request?.contract_version, 'ardaro.agent-invoice-matching.request.v1');
  rejectPaymentMetadata(fixture.request);
  const response = fixture.response;
  assert.equal(response?.contract_version, 'ardaro.agent-invoice-matching.response.v1');
  assert.equal(response.status, 'review_required');
  const result = response.result;
  assert.equal(result?.summary?.human_review_required, true);
  assert.equal(result.summary.payment_approved, false);
  assert.equal(result.summary.delivery_verified, false);
  const identity = 'res_' + createHash('sha256').update(JSON.stringify(canonical(result))).digest('hex');
  assert.equal(response.identities?.analysis_result_identity, identity, 'Synthetic result identity mismatch.');

  // Only the server's public synthetic request reaches this unsigned tool call.
  // No customer input, signer, payment metadata or retry exists in this demo.
  const unpaid = await client.callTool({ name: 'match_invoice', arguments: fixture.request });
  assert.equal(unpaid.isError, true, 'Expected payment-required, not paid processing.');
  const challenge = unpaid.structuredContent;
  assert.equal(challenge?.x402Version, 2);
  assert.equal(challenge.resource?.url, INVOICE_RESOURCE);
  assert.equal(challenge.accepts?.length, 1, 'Expected one payment option.');
  const offer = challenge.accepts[0];
  assert.equal(offer.scheme, 'exact');
  assert.equal(offer.network, 'eip155:8453');
  assert.equal(offer.amount, '500000');
  assert.equal(offer.asset?.toLowerCase(), USDC);
  assert.match(offer.payTo ?? '', /^0x[0-9a-fA-F]{40}$/);
  const text = unpaid.content?.find(item => item.type === 'text');
  assert.ok(text, 'Expected a text copy of the x402 challenge.');
  assert.deepEqual(JSON.parse(text.text), challenge);

  return {
    endpoint: MCP_ENDPOINT,
    tools: names,
    exampleKind: 'fixed synthetic fixture; no new analysis purchased',
    freeExample: fixture,
    reviewHandoff: {
      disposition: 'human_review_required',
      summary: result.summary,
      comparisonRows: result.comparison_rows,
      discrepancies: result.discrepancies,
      financialPostingPerformed: false,
      explanation: 'No discrepancies covers only supported checks on supplied data; it never approves payment.'
    },
    paymentChallenge: { resource: INVOICE_RESOURCE, network: offer.network, amountAtomic: offer.amount,
      price: '0.50 USDC', paymentSent: false, recipientIndependentlyVerified: false },
    checks: { discovery: 'passed', serviceStatus: 'passed', syntheticExample: 'passed',
      resultIdentity: 'passed', unpaidChallenge: 'passed' },
    paidSettlement: 'not attempted', fundsSpent: 0
  };
}
