import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';

test('real dashboard handlers keep UI, candle and P/L synchronized and reject late snapshot', async () => {
  const elements = new Map();
  const element = id => { if (!elements.has(id)) elements.set(id,{ textContent:'', innerHTML:'', className:'', addEventListener(){}, classList:{remove(){},add(){}} }); return elements.get(id); };
  let handlers, resolveSnapshot, candle;
  const series = { setData(){}, update(c){candle={...c};} };
  const context = vm.createContext({ console, Date, Set, Number, Math, JSON, setInterval(){}, clearInterval(){},
    document:{getElementById:element,querySelectorAll:()=>[]}, window:{matchMedia:()=>({matches:false})}, ResizeObserver:class{observe(){}} });
  const cache = new Map();
  const stubs = {
    './api.js': { fetchOHLC:async()=>[{time:1792584000,open:31,high:31,low:31,close:31}], fetchPositions:async()=>[{ticket:1,symbol:'XAGUSD-STD',side:'BUY',volume:0.5,open_price:31,swap:0,commission:0}],
      createTickWS: h=>{handlers=h;return {close(){}};}, fetchSnapshot:()=>new Promise(r=>{resolveSnapshot=r;}), closePosition(){},closeBulk(){} },
    'lightweight-charts':{createChart:()=>({addCandlestickSeries:()=>series,addHistogramSeries:()=>series,timeScale:()=>({fitContent(){}})})},
    './ui.js':{showToast(){},showConfirm(){}}
  };
  async function load(name){
    if(cache.has(name))return cache.get(name);
    let mod;
    if(stubs[name]){ const values=stubs[name];mod=new vm.SyntheticModule(Object.keys(values),function(){for(const [k,v] of Object.entries(values))this.setExport(k,v);},{context}); }
    else mod=new vm.SourceTextModule(await readFile(new URL(`../src/${name.replace('./','')}`,import.meta.url),'utf8'),{context});
    cache.set(name,mod); await mod.link(load); return mod;
  }
  const main=await load('./main.js');await main.evaluate();
  // Boot crosses the OHLC and positions awaits before installing handlers.
  for(let i=0;i<10 && !resolveSnapshot;i++)await new Promise(r=>setImmediate(r));
  assert.ok(handlers);assert.ok(resolveSnapshot);
  const data={price:32,bid:31.9,ask:32.1,market_asof:'2026-10-21T12:01:00Z'};
  handlers.onTick(data);
  const state=cache.get('./state.js').namespace.state;
  assert.equal(state.price,32);assert.equal(candle.close,32);assert.equal(state.realTickCount,1);
  assert.equal(element('price-value').textContent,'32.0000');
  assert.match(element('positions-body').innerHTML,/2500.00/);
  handlers.onTick({...data,price:'bad'});assert.equal(state.price,32);assert.equal(candle.close,32);
  handlers.onError({message:'upstream'});assert.equal(state.price,32);
  resolveSnapshot({price:30,bid:29.9,ask:30.1,asof:'2026-10-21T12:00:00Z'});
  await new Promise(r=>setImmediate(r));assert.equal(state.price,32);assert.equal(candle.close,32);
  handlers.onTick({...data,price:33,market_asof:'2026-10-21T12:02:00Z'});
  assert.equal(candle.close,33);assert.equal(state.realTickCount,2);assert.match(element('positions-body').innerHTML,/5000.00/);
  cache.get('./chart.js').namespace.processTick(NaN,true);assert.equal(candle.close,33);
});
