import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';

test('dashboard wiring keeps price card, candle, tick count and P/L synchronized through reconnect and HTTP race', async () => {
  const originals = Object.fromEntries(['document','window','localStorage','fetch','WebSocket','ResizeObserver','setInterval'].map(k=>[k,globalThis[k]]));
  const nodes = new Map(), sockets = [], updates = [];
  const element = id => {
    if (!nodes.has(id)) nodes.set(id, {textContent:'',innerHTML:'',className:'',style:{},
      classList:{add(){},remove(){},toggle(){}},addEventListener(){},clientWidth:800,clientHeight:400});
    return nodes.get(id);
  };
  globalThis.document={getElementById:element,querySelectorAll:()=>[]};
  globalThis.window={location:{origin:'https://aura.invalid',href:'https://aura.invalid/'},
    matchMedia:()=>({matches:false}),addEventListener(){}};
  globalThis.localStorage={getItem:()=>null};
  globalThis.ResizeObserver=class {observe(){}};
  globalThis.setInterval=()=>0;
  globalThis.WebSocket=class {
    constructor(url){this.url=url;sockets.push(this);}
    close(){this.onclose?.();}
    sendMessage(msg){this.onmessage({data:JSON.stringify(msg)});}
  };
  let resolveSnapshot;
  globalThis.fetch=async url => ({ok:true,json:()=>url.includes('/ohlc') ?
    [{time:Math.floor(Date.now()/60000)*60,open:30,high:30,low:30,close:30,volume:1}] :
    new Promise(resolve=>{resolveSnapshot=resolve;})});
  globalThis.__chartUpdates=updates;
  const chartMock = 'data:text/javascript,' + encodeURIComponent(
    'export function createChart(){const series=()=>({setData(){},update(c){globalThis.__chartUpdates.push({...c})}});return {addCandlestickSeries:series,addHistogramSeries:series,timeScale:()=>({fitContent(){}}),applyOptions(){}}}');
  const uiMock = 'data:text/javascript,export function showToast(){};export async function showConfirm(){return false}';
  const hooks=registerHooks({
    resolve(specifier,context,next){
      if(specifier==='lightweight-charts') return {url:chartMock,shortCircuit:true};
      if(specifier==='./ui.js') return {url:uiMock,shortCircuit:true};
      return next(specifier,context);
    },
    load(url,context,next){
      if(url.endsWith('/src/api.js')) return {format:'module',source:readFileSync(new URL(url),'utf8').replaceAll('import.meta.env','({})'),shortCircuit:true};
      return next(url,context);
    },
  });
  try {
    await import('../src/main.js');
    // Actual fetchPositions stub uses a 150ms delay during boot.
    await new Promise(resolve=>setTimeout(resolve,200));
    assert.equal(sockets.length,1);
    assert.equal(sockets[0].url,'wss://aura.invalid/api/xag/ws/tick');
    const {state}=await import('../src/state.js');
    const tick={price:32.05,bid:31.9,ask:32.1,market_asof:'2026-10-21T12:00:00Z'};
    sockets[0].onopen();
    sockets[0].sendMessage({type:'tick',data:tick});
    assert.equal(state.price,32.05);
    assert.equal(element('price-value').textContent,'32.0500');
    assert.equal(updates.at(-1).close,32.05);
    assert.equal(state.realTickCount,1);
    assert.match(element('positions-body').innerHTML,/32.0500/);
    assert.match(element('positions-body').innerHTML,/\+\$1375.00/);
    for(const type of ['ping','pong','error','unknown','bar_close'])
      sockets[0].sendMessage({type,data:{price:999}});
    sockets[0].sendMessage({type:'tick',data:{...tick,price:'oops'}});
    assert.equal(state.price,32.05);assert.equal(updates.length,1);
    // The delayed initial HTTP snapshot must not roll back a live quote.
    resolveSnapshot({...tick,price:20,bid:19,ask:21,rsi_1m:50,rsi_15m:50,rsi_1h:50});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(state.price,32.05);assert.equal(updates.length,1);
    sockets[0].onclose();
    await new Promise(resolve=>setTimeout(resolve,1050));
    assert.equal(sockets.length,2);
    sockets[1].onopen();
    sockets[1].sendMessage({type:'tick',data:{...tick,price:32.1}});
    assert.equal(element('price-value').textContent,'32.1000');
    assert.equal(updates.at(-1).close,32.1);assert.equal(state.realTickCount,2);
    assert.match(element('positions-body').innerHTML,/\+\$1500.00/);
    sockets[0].sendMessage({type:'tick',data:{...tick,price:99}});
    assert.equal(state.price,32.1);
  } finally {
    hooks.deregister();
    for(const [k,v] of Object.entries(originals)) {if(v===undefined) delete globalThis[k];else globalThis[k]=v;}
    delete globalThis.__chartUpdates;
  }
});
