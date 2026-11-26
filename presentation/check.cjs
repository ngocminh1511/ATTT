'use strict';
// No browser dependency: verify data-driven render and navigation, not visual layout.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createDeck,pct} = require('./src/app.js');
const base = __dirname;
const content = JSON.parse(fs.readFileSync(path.join(base,'src/slides.json'),'utf8'));
const data = JSON.parse(fs.readFileSync(path.join(base,'data/snapshot.json'),'utf8'));
const deck = createDeck({content,data});
let checks=0;
function check(name, test) { test(); checks++; process.stdout.write(`OK ${name}\n`); }

check('26 pages, 9 stages, no appendix',()=>{
  assert.equal(deck.slides.length,26);assert.equal(deck.groups.length,9);assert.equal(deck.appendix.length,0);
  assert.deepEqual(deck.groups.map(s=>s.slides.length),[1,3,2,1,2,4,5,4,1]);
});
check('all audience pages render without presenter instructions',()=>{
  for(const slide of deck.slides) {
    const html=deck.render(slide.id);
    assert.ok(html.length>200,slide.id);
    assert.ok(!/NaN|Infinity|undefined|__PAYLOAD__/.test(html),slide.id);
    for(const match of html.matchAll(/href="#([^"]+)"/g))assert.ok(deck.byId.has(match[1]),`${slide.id} → ${match[1]}`);
    assert.ok(!/ĐIỂM CẦN TRÌNH BÀY|SAU BƯỚC NÀY|source-mini|takeaway|speaker-notes/.test(html),slide.id);
    if(slide.stage!=='appendix'){
      assert.ok(!html.includes('fl_ddos/'),slide.id);
      if(!['data','clean'].includes(slide.stage))assert.ok(!html.includes('<table'),`${slide.id}: main deck must explain with visuals, not reference tables`);
    }
    assert.ok(deck.renderMenu(slide.id).includes('aria-current="page"'));
  }
});
check('source and metric combinations do not lose values',()=>{
  for(const id of ['results-scoreboard','results-review','results-confusion']) {
    for(const source of ['cicddos2019','unsw_nb15','mean_over_sources','worst_source','pooled_predictions']) {
      for(const metric of ['f1_macro_present','dos_f1','attack_far_benign','attack_recall','dos_recall','attack_roc_auc']) {
        assert.ok(!/NaN|Infinity|undefined/.test(deck.render(id,{source,metric})),`${id}/${source}/${metric}`);
      }
    }
  }
  for(const method of Object.keys(data.methods))for(const testSource of data.sources)for(const matrixMode of ['percent','count']) {
    assert.ok(!/NaN|undefined/.test(deck.render('results-confusion',{method,testSource,matrixMode})));
  }
  assert.ok(['60,89%','56,99%','50,26%','3,01%','Local · UNSW #4'].every(x=>deck.render('results-scoreboard').includes(x)));
  assert.ok(['Client 1','Client 2','Client 3','Client 4','18.236','18.237'].every(x=>deck.render('split-clients').includes(x))&&deck.render('train-round',{step:3}).includes('0,25'));
  for(const id of ['local_c1','local_c2','local_c3','local_c4'])assert.ok(deck.render('results-scoreboard').includes(id==='local_c1'?'CIC #1':id==='local_c2'?'CIC #2':id==='local_c3'?'UNSW #3':'UNSW #4'));
  assert.ok(deck.render('results-review').includes('16,96%')&&deck.render('results-metrics').includes('FAR'));
  for(const rankingSource of ['pooled','client_1','client_2','client_3','client_4']){assert.ok(!/NaN/.test(deck.render('select-ranking',{rankingSource})));}
  const overview=deck.render('data-problem'),cic=overview,unsw=overview;
  assert.ok(overview.includes('431.371')&&overview.includes('257.673')&&overview.includes('121.368')&&overview.includes('93.000'));
  assert.ok(cic.includes('12/01/2019')&&cic.includes('11/03/2019')&&cic.includes('Portmap')&&!cic.includes('SSDP'));
  assert.ok(unsw.includes('175.341')&&unsw.includes('82.332')&&overview.includes('<b>45</b>'));
  const corrHtml=deck.render('select-corr');assert.ok(['0,977','0,953','0,986','0,998'].every(v=>corrHtml.includes(v)));
  assert.ok(deck.render('select-sets').includes('bwd_packets_s')&&deck.render('select-das').includes('0,001'));
  const schema=deck.render('clean-schema'),quality=deck.render('clean-labels')+deck.render('clean-quality');
  for(const col of ['Flow Duration','dur','sinpkt / dinpkt','µs ÷ 10⁶','ms ÷ 10³','protocol_group'])assert.ok(schema.includes(col),col);
  for(const cls of data.classes)assert.ok(quality.includes(cls),cls);assert.ok(quality.includes('Loại dòng')&&quality.includes('Gán missing')&&quality.includes('Dừng pipeline'));
  for(const attack of data.dataset_catalog.unsw_nb15.attacks)assert.ok(unsw.includes(attack));
});
check('hash, forward/back and endpoints',()=>{
  assert.equal(deck.resolveId('#results-scoreboard'),'results-scoreboard');
  assert.equal(deck.resolveId('#bad-id'),'pipeline');
  assert.equal(deck.resolveId('#%E0%A4%A'),'pipeline');
  assert.equal(deck.neighbor('cover',-1),'cover');assert.equal(deck.neighbor('cover',1),'pipeline');assert.equal(deck.resolveId(''),'cover');
  assert.equal(deck.neighbor('pipeline',-1),'cover');
  assert.equal(deck.neighbor('pipeline',1),'data-problem');
  assert.equal(deck.neighbor('demo-architecture',1),'thanks');assert.equal(deck.neighbor('thanks',1),'thanks');assert.ok(deck.render('thanks').includes('Cảm ơn thầy cô'));
  assert.equal(deck.neighbor('results-review',1),'demo-architecture');
  for(let i=0;i<deck.slides.length-1;i++)assert.equal(deck.neighbor(deck.slides[i].id,1),deck.slides[i+1].id);
});
check('disabled page/stage is skipped without broken links',()=>{
  const changed=structuredClone(content);
  changed.slides.forEach(s=>{if(s.id==='results-review'||s.stage==='normalize')s.enabled=false;});
  const d=createDeck({content:changed,data});
  assert.equal(d.slides.length,23);assert.equal(d.groups.length,8);
  assert.equal(d.neighbor('results-confusion',1),'demo-architecture');
  assert.equal(d.neighbor('features-map',1),'select-das');
  for(const s of d.slides)for(const match of d.render(s.id).matchAll(/href="#([^"]+)"/g))assert.ok(d.byId.has(match[1]),`${s.id} → ${match[1]}`);
  assert.ok(!d.nav('pipeline').includes('normalize-log'));
});
check('absent class is N/A; complete validation history and histogram',()=>{
  assert.equal(pct(null),'N/A');assert.equal(pct(0),'0,00%');
  assert.equal(data.histogram.raw.counts.reduce((a,b)=>a+b,0),200000);
  assert.equal(data.histogram.log.counts.reduce((a,b)=>a+b,0),200000);
  for(const id of ['all','das','prox']) {
    assert.equal(data.methods[id].rounds.length,30);
    assert.equal(new Set(data.methods[id].rounds.map(r=>r.round)).size,30);
  }
});
check('compiled HTML is standalone and speaker script matches source',()=>{
  const html=fs.readFileSync(path.join(base,'index.html'),'utf8');
  const script=fs.readFileSync(path.join(base,'kich_ban.md'),'utf8');
  assert.ok(!/<(?:script|link)\b[^>]*(?:src|href)\s*=/i.test(html));
  assert.ok(!/\bfetch\s*\(|\bXMLHttpRequest\b|@import\b|url\s*\(\s*['"]?(?:https?:|\/\/)/.test(html));
  assert.ok(!html.includes('__PAYLOAD__'));assert.ok(html.includes('lang="vi"'));
  const inline=JSON.parse(html.match(/<script type="application\/json" id="deck-payload">([\s\S]*?)<\/script>/)[1]);
  const visibleFields=['id','number','stage','enabled','view','title','message'];
  const projected={title:content.title,stages:content.stages.map(s=>Object.fromEntries(Object.entries(s).filter(([k])=>k!=='output'))),slides:content.slides.map(s=>Object.fromEntries(visibleFields.map(k=>[k,s[k]])))};
  assert.deepEqual(inline.content,projected);assert.deepEqual(inline.data,data);
  assert.ok(inline.assets.logo.startsWith('data:image/png;base64,'));
  const projectedDeck=createDeck(inline);
  const cover=projectedDeck.render('cover');assert.ok(['Nguyễn Tấn Khôi','102230120','102230157','animateMotion'].every(x=>cover.includes(x)));
  const imageSrc=cover.match(/<img src="([^"]+)"/)[1];
  assert.ok(imageSrc.startsWith('data:image/png;base64,'));
  for(const s of projectedDeck.slides)assert.ok(!/undefined|NaN/.test(projectedDeck.render(s.id).replace(/data:image\/png;base64,[^"]+/g,'[embedded image]')),s.id);
  assert.ok(!/notes-toggle|speaker-notes|ĐIỂM CẦN TRÌNH BÀY|SAU BƯỚC NÀY/.test(html));
  assert.ok(inline.content.slides.every(s=>!('speech' in s)&&!('point' in s)&&!('sources' in s)));
  for(const s of content.slides)assert.ok(script.includes(s.speech),s.id);
});

// Exercise mount wiring in a small DOM double. This checks event behavior only.
check('mounted next/back/hash, selectors, menu, keyboard and loop step',()=>{
  const listeners={},windowListeners={};
  class Element {
    constructor(id){this.id=id;this.innerHTML='';this.textContent='';this.hidden=['slide-menu','backdrop'].includes(id);this.disabled=false;this.dataset={};this.style={};this.attributes={};this.handlers={};}
    addEventListener(type,fn){this.handlers[type]=fn;}
    setAttribute(k,v){this.attributes[k]=v;}
    focus(){doc.activeElement=this;}
    querySelector(){return new Element('child');}
    querySelectorAll(){return [];}
    contains(){return false;}
    closest(){return null;}
  }
  const ids=['main','slide-menu','backdrop','menu-toggle','fullscreen','previous','next','position','page-number','progress','stage-nav','toast'];
  const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
  const doc={getElementById:id=>elements[id]||null,addEventListener:(k,v)=>listeners[k]=v,activeElement:elements.main,
    body:{classList:{add(){},remove(){},toggle(){}}},documentElement:{requestFullscreen:async()=>{}},exitFullscreen:async()=>{},fullscreenElement:null};
  let hash='#pipeline';
  const location={get hash(){return hash;},set hash(v){hash=v.startsWith('#')?v:'#'+v;windowListeners.hashchange?.();}};
  const context={document:doc,location,history:{replaceState(_,__,v){hash=v;}},console,addEventListener:(k,v)=>windowListeners[k]=v};
  vm.runInNewContext(fs.readFileSync(path.join(base,'src/visuals.js'),'utf8')+'\n'+fs.readFileSync(path.join(base,'src/app.js'),'utf8'),context);
  context.Presentation.mount({content,data});
  assert.ok(elements.main.innerHTML.includes('pipeline-map'));
  elements.next.handlers.click();assert.equal(hash,'#data-problem');assert.ok(elements.previous.disabled===false);
  elements.previous.handlers.click();assert.equal(hash,'#pipeline');assert.ok(!elements.previous.disabled);
  elements.previous.handlers.click();assert.equal(hash,'#cover');assert.ok(elements.previous.disabled);location.hash='#pipeline';
  elements['menu-toggle'].handlers.click();assert.equal(elements['slide-menu'].hidden,false);
  assert.equal(elements['menu-toggle'].attributes['aria-expanded'],'true');
  const key=k=>listeners.keydown({key:k,target:elements.main,preventDefault(){}});
  key('Escape');assert.equal(elements['slide-menu'].hidden,true);
  key('n');assert.equal(elements['slide-menu'].hidden,true);
  key('ArrowRight');assert.equal(hash,'#data-problem');key('h');assert.equal(hash,'#pipeline');
  location.hash='#results-scoreboard';
  assert.ok(elements.main.innerHTML.includes('FAR ↓'));
  assert.ok(elements.main.innerHTML.includes('16,96%'));
  elements['menu-toggle'].handlers.click();location.hash='#results-review';
  assert.ok(elements['slide-menu'].innerHTML.includes('Nhận xét: ưu và nhược'));
  key('Escape');location.hash='#train-round';
  const action={dataset:{action:'step',value:'3'}};
  listeners.click({target:{closest:selector=>selector==='[data-action]'?action:null}});
  assert.ok(elements.main.innerHTML.includes('data-value="3" class="active" aria-current="step"'));
  location.hash='#clean-schema';
  const phaseAction={dataset:{action:'phase',value:'1'}};
  listeners.click({target:{closest:selector=>selector==='[data-action]'?phaseAction:null}});
  assert.ok(elements.main.innerHTML.includes('fwd_packets'));
  assert.ok(elements.main.innerHTML.includes('spkts'));
  location.hash='#results-review';
  elements.main.handlers.change({target:{dataset:{control:'focus'},value:'prox'}});
  assert.ok(elements.main.innerHTML.includes('rv-card on'));
  location.hash='#unknown';assert.equal(hash,'#pipeline');
});
process.stdout.write(`\n${checks} groups passed. Browser layout/fullscreen/offline require a real browser for visual confirmation.\n`);
