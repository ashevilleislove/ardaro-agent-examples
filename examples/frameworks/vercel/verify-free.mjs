// Actual AI SDK MCP adapter execution. The fetch boundary admits only this
// endpoint, lifecycle/discovery RPCs and two fixed examples with empty inputs.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createMCPClient} from '@ai-sdk/mcp';
import {z} from 'zod';
const endpoint='https://agents.getardaro.com/mcp';
const allowed=new Set(['get_receipt_example','get_invoice_matching_example']);
const calls=[],responses={};let discoveryCount=0,client;
const nativeFetch=globalThis.fetch;
const canonical=value=>JSON.stringify(value===null||typeof value!=='object'?value:Array.isArray(value)?value.map(v=>JSON.parse(canonical(v))):Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])));
const identity=value=>'res_'+createHash('sha256').update(canonical(value)).digest('hex');
async function guardedFetch(input,init={}) {
  const url=typeof input==='string'?input:input instanceof URL?input.href:input.url;
  assert.equal(url,endpoint,'No other endpoint allowed');
  assert.ok(calls.length<20,'Bounded request count exceeded');
  const headers=new Headers(init.headers??(input instanceof Request?input.headers:undefined));
  for(const key of headers.keys())assert.ok(!/authorization|payment|api-key/i.test(key),'Credential/payment header blocked');
  const method=init.method??(input instanceof Request?input.method:'GET');
  let rpc=null;
  if(method==='POST') {
    const body=typeof init.body==='string'?init.body:input instanceof Request?await input.clone().text():null;
    assert.equal(typeof body,'string');rpc=JSON.parse(body);
    assert.ok(['server/discover','initialize','notifications/initialized','tools/list','tools/call','ping'].includes(rpc.method),'Unapproved RPC');
    assert.ok(!JSON.stringify(rpc.params?._meta??{}).includes('x402'),'Payment metadata blocked');
    if(rpc.method==='tools/call'){assert.ok(allowed.has(rpc.params.name));assert.deepEqual(rpc.params.arguments??{},{});assert.ok(!calls.some(c=>c.tool===rpc.params.name),'Only one call per free fixture');}
  } else assert.ok(['GET','DELETE'].includes(method),'Unapproved transport method');
  const entry={http_method:method,rpc_method:rpc?.method??null,tool:rpc?.method==='tools/call'?rpc.params.name:null};calls.push(entry);
  const response=await nativeFetch(input,{...init,redirect:'error',signal:AbortSignal.any([...(init.signal?[init.signal]:[]),AbortSignal.timeout(20000)])});entry.http_status=response.status;
  if(rpc?.method==='tools/list'&&response.ok){const raw=await response.clone().json();discoveryCount=raw.result?.tools?.length??0;}
  return response;
}
const config=JSON.parse(await readFile(new URL('./vercel.connection.json',import.meta.url),'utf8'));
assert.deepEqual(config,{transport:{type:'http',url:endpoint}});
const report={framework:'Vercel AI SDK MCP',status:'FAIL',endpoint,started_at:new Date().toISOString(),node:process.version,packages:{'@ai-sdk/mcp':JSON.parse(await readFile(new URL('./node_modules/@ai-sdk/mcp/package.json',import.meta.url),'utf8')).version,zod:JSON.parse(await readFile(new URL('./node_modules/zod/package.json',import.meta.url),'utf8')).version},model_calls:0,paid_tool_calls:0,wallet_operations:0,cost_usdc:'0.00'};
try {
  client=await createMCPClient({...config,transport:{...config.transport,fetch:guardedFetch},maxRetries:0});
  report.server_info=client.serverInfo;report.protocol_version=client.initializeResult.protocolVersion;
  const tools=await client.tools({schemas:{get_receipt_example:{inputSchema:z.object({}).strict()},get_invoice_matching_example:{inputSchema:z.object({}).strict()}}});
  assert.deepEqual(Object.keys(tools).sort(),[...allowed].sort());
  for(const name of allowed){const result=await tools[name].execute({}, {toolCallId:name,messages:[]});assert.notEqual(result.isError,true);const fixture=result.structuredContent;assert.equal(fixture?.synthetic_only,true);const response=fixture.expected_response??fixture.response;assert.equal(response?.status,'review_required');assert.equal(response.identities.analysis_result_identity,identity(response.result));responses[name]=result;}
  report.status='PASS';report.discovered_tool_count=discoveryCount;report.free_examples_verified=[...allowed];
} catch(error){report.error={name:error.name,message:error.message};process.exitCode=1;}
finally {if(client)await client.close();report.finished_at=new Date().toISOString();report.calls=calls;await writeFile('execution-report.json',JSON.stringify(report,null,2)+'\n','utf8');await writeFile('free-results.json',JSON.stringify(responses,null,2)+'\n','utf8');console.log(JSON.stringify(report));}
