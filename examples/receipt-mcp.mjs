import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { MCP_ENDPOINT, createNoSpendFetch, runReceiptDemo } from '../src/receipt-demo.mjs';

const client = new Client({ name: 'ardaro-public-receipt-example', version: '1.0.0' });
try {
  if (process.argv.length > 2) throw new Error('This fixed, no-spend demo takes no arguments.');
  const transport = new StreamableHTTPClientTransport(new URL(MCP_ENDPOINT), {
    fetch: createNoSpendFetch(),
    reconnectionOptions: {
      maxRetries: 0, initialReconnectionDelay: 1000,
      maxReconnectionDelay: 1000, reconnectionDelayGrowFactor: 1
    }
  });
  await client.connect(transport);
  console.log(JSON.stringify(await runReceiptDemo(client), null, 2));
} catch (error) {
  console.error(`Demo failed: ${error.message}`);
  console.error('No payment was authorized. Check the endpoint and public integration instructions.');
  process.exitCode = 1;
} finally {
  await client.close();
}
