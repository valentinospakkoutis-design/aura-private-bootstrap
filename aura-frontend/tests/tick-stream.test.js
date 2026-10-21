import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validQuote, applyQuote, openTickStream } from '../src/tick-stream.js';
const quote = { price: 31.8, bid: 31.7, ask: 31.9, market_asof: '2026-10-21T12:00:00Z' };
function setup() {
  const sockets = [], timers = new Map(), ticks = [], bars = [], errors = [], statuses = [];
  let token = 'first', id = 0;
  class WS {
    constructor(url) { this.url = url; sockets.push(this); }
    close() { this.onclose({ code: 1000 }); }
    sendMessage(msg) { this.onmessage({ data: JSON.stringify(msg) }); }
  }
  const controller = openTickStream({ url: 'wss://example.test/api/xag/ws/tick', getToken: () => token,
    WebSocketImpl: WS, schedule: (fn, delay) => { timers.set(++id, { fn, delay }); return id; }, cancel: n => timers.delete(n),
    onTick: q => ticks.push(q), onBarClose: b => bars.push(b), onError: e => errors.push(e), onStatusChange: s => statuses.push(s) });
  return { sockets, timers, ticks, bars, errors, statuses, controller, token: t => { token = t; }, run() { const [n,t] = timers.entries().next().value; timers.delete(n); t.fn(); } };
}
test('nested backend quote is extracted; backend price is authoritative', () => {
  const h = setup(); h.sockets[0].sendMessage({ type: 'tick', data: quote });
  assert.deepEqual(h.ticks, [quote]); const state = {};
  assert.equal(applyQuote(state, h.ticks[0]), true); assert.equal(state.price, quote.price);
});
for (const field of ['bid','ask','price']) {
  for (const value of [undefined, null, '31.8', '', true, NaN, Infinity, -1, 0]) {
    test(`reject ${field}=${String(value)}`, () => {
      const data = { ...quote, [field]: value }, h = setup(), state = { ...quote };
      assert.equal(validQuote(data), false); assert.equal(applyQuote(state, data), false);
      h.sockets[0].sendMessage({ type: 'tick', data }); assert.equal(h.ticks.length, 0);
      assert.deepEqual(state, quote);
    });
  }
}
test('reject crossed market, missing object and legacy flat tick', () => {
  const h = setup();
  for (const data of [null, [], {}, { ...quote, bid: 33 }]) h.sockets[0].sendMessage({ type: 'tick', data });
  h.sockets[0].sendMessage(quote); assert.deepEqual(h.ticks, []);
});
test('mixed control messages and malformed JSON preserve the last good quote', () => {
  const h = setup(), ws = h.sockets[0];
  ws.sendMessage({ type: 'tick', data: quote });
  for (const msg of [{ type:'ping' }, { type:'pong' }, { type:'unknown', data:quote }, null, [],
    { type:'error', message:'unavailable' }, { type:'bar_close', timeframe:'1m', market_asof:quote.market_asof }]) ws.sendMessage(msg);
  ws.onmessage({ data:'{' }); ws.sendMessage({ type:'bar_close', timeframe:'1m', market_asof:'bad' });
  assert.equal(h.ticks.length, 1); assert.equal(h.bars.length, 1); assert.equal(h.errors.length, 1);
  ws.sendMessage({ type:'tick', data:{ ...quote, price:32 } }); assert.equal(h.ticks.at(-1).price,32);
});
test('reconnect uses latest token, ignores old socket and accepts new ticks', () => {
  const h = setup(), old = h.sockets[0]; old.onopen(); old.onclose({ code:1006 });
  old.onclose({ code:1006 }); assert.equal(h.timers.size,1); h.token('new token'); h.run();
  const ws = h.sockets[1]; assert.ok(ws.url.endsWith('?token=new%20token'));
  old.sendMessage({ type:'tick', data:quote }); assert.equal(h.ticks.length,0);
  ws.onopen(); ws.sendMessage({ type:'tick', data:quote }); assert.equal(h.ticks.length,1);
  ws.onclose({code:1006}); assert.equal([...h.timers.values()][0].delay,1000);
  h.controller.close(); assert.equal(h.timers.size,0); ws.sendMessage({type:'tick',data:quote}); assert.equal(h.ticks.length,1);
});
test('intentional close never reconnects', () => {
  const h=setup(); h.controller.close(); h.controller.close(); assert.equal(h.timers.size,0);
  assert.equal(h.statuses.at(-1),'disconnected');
});
test('auth failure stops retries', () => {
  const h=setup(); h.sockets[0].onclose({code:4001}); assert.equal(h.timers.size,0); assert.equal(h.statuses.at(-1),'disconnected');
});
test('backoff is capped', () => {
  const h=setup(); for(let i=0;i<8;i++){h.sockets.at(-1).onclose({code:1006}); assert.ok([...h.timers.values()][0].delay<=30000); h.run();}
});
test('older market data cannot overwrite a newer quote', () => {
  const state={}; applyQuote(state,quote);
  assert.equal(applyQuote(state,{...quote,price:30,market_asof:'2026-10-21T11:59:00Z'}),false);
  assert.equal(state.price,quote.price);
});
