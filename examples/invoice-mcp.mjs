import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { MCP_ENDPOINT, createNoSpendFetch } from '../src/receipt-demo.mjs';
import { runInvoiceDemo } from '../src/invoice-demo.mjs';

const client = new Client({ name: 'ardaro-public-invoice-example', version: '1.1.0' });
try {
  if (process.argv.length > 2) throw new Error('This fixed, no-spend demo takes no arguments.');
  const transport = new StreamableHTTPClientTransport(new URL(MCP_ENDPOINT), {
    fetch: createNoSpendFetch(),
    reconnectionOptions: { maxRetries: 0, initialReconnectionDelay: 1000,
      maxReconnectionDelay: 1000, reconnectionDelayGrowFactor: 1 }
  });
  await client.connect(transport);
  console.log(JSON.stringify(await runInvoiceDemo(client), null, 2));
} catch (error) {
  console.error(`Invoice demo failed: ${error.message}`);
  console.error('No payment was authorized. Check the live service contract; do not attach a wallet to bypass this check.');
  process.exitCode = 1;
} finally {
  await client.close();
}
