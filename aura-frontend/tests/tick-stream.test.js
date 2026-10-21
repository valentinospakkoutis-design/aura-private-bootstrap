import test from 'node:test';
import assert from 'node:assert/strict';
import { openTickStream } from '../src/tick-stream.js';
import { normalizeQuote, applyQuote } from '../src/quotes.js';

const quote = {price: 32, bid: 31.9, ask: 32.1, market_asof: '2026-10-21T12:00:00Z'};
function harness(options = {}) {
  const sockets = [], jobs = new Map(), ticks = [], statuses = [], bars = [], errors = [];
  let id = 0;
  class Socket {
    constructor(url) { this.url = url; sockets.push(this); }
    close() { this.onclose?.(); }
    send(message) { this.onmessage({ data: typeof message === 'string' ? message : JSON.stringify(message) }); }
  }
  const stream = openTickStream({url: () => 'wss://example.invalid/api/xag/ws/tick',
    WebSocketImpl: Socket, schedule(fn, delay) {jobs.set(++id, {fn, delay}); return id;},
    cancel(key) { jobs.delete(key); }, random: () => 0,
    onTick: t => ticks.push(t), onStatusChange: s => statuses.push(s),
    onBarClose: b => bars.push(b), onError: e => errors.push(e), ...options});
  return {sockets, jobs, ticks, statuses, bars, errors, stream,
    run() {const [key, {fn}] = jobs.entries().next().value; jobs.delete(key); fn();}};
}

test('backend envelope is unwrapped and metadata retained', () => {
  const h = harness(); h.sockets[0].send({type:'tick', data:quote});
  assert.deepEqual(h.ticks, [{price:32,bid:31.9,ask:32.1,priceAsof:quote.market_asof,stale:false}]);
  h.stream.close();
});
for (const key of ['price', 'bid', 'ask']) {
  test('missing ' + key + ' rejects entire quote', () => {
    const data = {...quote}; delete data[key];
    assert.equal(normalizeQuote(data), null);
  });
  test('invalid numeric ' + key + ' rejects entire quote', () => {
    for (const value of [null, undefined, '32', '', true, NaN, Infinity, -Infinity, {}, [], 0, -1]) {
      assert.equal(normalizeQuote({...quote, [key]:value}), null);
    }
  });
}
test('malformed, unknown, legacy flat messages and invalid data never become ticks', () => {
  const h = harness();
  for (const msg of ['{', 'null', '[]', '42', {}, {type:'tick'}, {type:'tick', data:[]},
    {type:'future',data:quote}, {...quote,type:'tick'}, {type:'tick', data:{...quote,bid:33}}]) h.sockets[0].send(msg);
  assert.equal(h.ticks.length,0);
});
test('alternating types dispatch without changing quotes', () => {
  const h = harness(), s=h.sockets[0];
  s.send({type:'tick',data:quote});
  for(const type of ['ping','pong','bar_close','error','future']) s.send({type,data:{price:999},message:'upstream unavailable'});
  s.send({type:'tick',data:{...quote,price:32.05}});
  assert.deepEqual(h.ticks.map(t=>t.price),[32,32.05]);
  assert.equal(h.bars.length,1); assert.equal(h.errors.length,1);
});
test('reconnect ignores retired socket callbacks and accepts new ticks', () => {
  const h=harness(), old=h.sockets[0];
  old.onopen(); old.send({type:'tick',data:quote}); old.onclose(); old.onclose();
  assert.equal(h.jobs.size,1); assert.equal([...h.jobs.values()][0].delay,1000);
  h.run(); const next=h.sockets[1]; next.onopen();
  old.send({type:'tick',data:{...quote,price:999}}); old.onclose(); old.onopen();
  next.send({type:'tick',data:{...quote,price:32.2}});
  assert.deepEqual(h.ticks.map(t=>t.price),[32,32.2]); assert.equal(h.jobs.size,0);
});
test('backoff caps at 30s and resets after open', () => {
  const h=harness();
  for(let i=0;i<8;i++) {h.sockets.at(-1).onclose(); assert.ok([...h.jobs.values()][0].delay<=30000);h.run();}
  h.sockets.at(-1).onopen();h.sockets.at(-1).onclose();
  assert.equal([...h.jobs.values()][0].delay,1000);
});
test('explicit close cancels retry and never reconnects', () => {
  const h=harness(), old=h.sockets[0];old.onclose();h.stream.close();h.stream.close();
  assert.equal(h.jobs.size,0);old.onclose();old.onopen();old.send({type:'tick',data:quote});
  assert.equal(h.jobs.size,0);assert.equal(h.ticks.length,0);assert.equal(h.statuses.at(-1),'disconnected');
});
test('close of open socket does not schedule retry', () => {
  const h=harness();h.sockets[0].onopen();h.stream.close();assert.equal(h.jobs.size,0);
});
test('transport error reports once; close owns retry', () => {
  const h=harness();h.sockets[0].onerror();assert.equal(h.errors.length,1);assert.equal(h.jobs.size,0);
  h.sockets[0].onclose();assert.equal(h.jobs.size,1);
});
test('constructor failure is retried and can be cancelled', () => {
  const jobs=new Map(), errors=[];
  const stream=openTickStream({url:()=>{throw Error('bad URL');},onTick(){},
    onError:e=>errors.push(e),schedule(fn,delay){jobs.set(1,{fn,delay});return 1;},cancel:k=>jobs.delete(k)});
  assert.equal(errors.length,1);assert.equal(jobs.size,1);stream.close();assert.equal(jobs.size,0);
});
test('atomic state, chart and P/L effects use backend price rather than midpoint', () => {
  const state={anchor:null,price:30,bid:29,ask:31}, seen=[];
  const effects={updatePriceUI:()=>seen.push(['ui',state.price,state.bid,state.ask]),
    processTick:(price,real)=>seen.push(['chart',price,real]),
    renderPositions:()=>seen.push(['pl',(state.price-30)*0.5*5000])};
  assert.equal(applyQuote(state,{...quote,price:32.05},effects),true);
  assert.deepEqual(seen,[['ui',32.05,31.9,32.1],['chart',32.05,true],['pl',(32.05-30)*2500]]);
  const before=structuredClone(state);seen.length=0;
  assert.equal(applyQuote(state,{...quote,ask:null},effects),false);
  assert.deepEqual(state,before);assert.deepEqual(seen,[]);
});
test('older timestamp cannot roll back accepted quote', () => {
  const state={anchor:null},effects={updatePriceUI(){},processTick(){},renderPositions(){}};
  applyQuote(state,quote,effects);
  assert.equal(applyQuote(state,{...quote,price:20,market_asof:'2026-10-20T12:00:00Z'},effects),false);
  assert.equal(state.price,32);
});
