/* period-agg v2: 날짜 하단 기간 버튼 (오늘/1주일/저번달/이번달/1개월/3개월)
   기간 선택 → 해당 일자 페이지들의 D를 내려받아 합산 → 같은 페이지 렌더러로 전 섹션 재렌더(iframe 오버레이).
   오늘 = 일일 보기(원래 화면). */
(function(){
var BTNS=[['today','오늘'],['w1','1주일'],['lastm','저번달'],['thism','이번달'],['m1','1개월'],['m3','3개월']];
var IN_AGG=!!window.__PAGG;
var dCache={}, tries=0;

function pad(n){return(n<10?'0':'')+n}
function fmtD(d){return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())}
function parseD(s){var p=s.split('-');return new Date(+p[0],+p[1]-1,+p[2])}
function anchor(){
  var el=document.getElementById('dnLabel');
  var m=el&&el.textContent.match(/(\d{4}-\d{2}-\d{2})/);
  if(m)return m[1];
  m=document.title.match(/(\d{4}-\d{2}-\d{2})/); if(m)return m[1];
  m=location.pathname.match(/(\d{4}-\d{2}-\d{2})\.html/); return m?m[1]:null;
}
function range(key,cur){
  var d=parseD(cur),s,e;
  if(key==='w1'){s=new Date(d);s.setDate(s.getDate()-6);e=d}
  else if(key==='lastm'){s=new Date(d.getFullYear(),d.getMonth()-1,1);e=new Date(d.getFullYear(),d.getMonth(),0)}
  else if(key==='thism'){s=new Date(d.getFullYear(),d.getMonth(),1);e=d}
  else if(key==='m1'){s=new Date(d);s.setDate(s.getDate()-29);e=d}
  else{s=new Date(d);s.setDate(s.getDate()-89);e=d}
  return [fmtD(s),fmtD(e)]
}
function label(key){for(var i=0;i<BTNS.length;i++)if(BTNS[i][0]===key)return BTNS[i][1];return key}

/* ===== D 추출 ===== */
function extractD(html){
  var i=html.indexOf('const D =');
  if(i<0)return null;
  var j=html.indexOf('\n',i); if(j<0)j=html.length;
  var seg=html.slice(i,j);
  var a=seg.indexOf('{'), b=seg.lastIndexOf('}');
  if(a<0||b<0)return null;
  try{return JSON.parse(seg.slice(a,b+1))}catch(e){return null}
}
function fetchDay(date){
  if(dCache[date])return Promise.resolve(dCache[date]);
  return fetch(date+'.html').then(function(r){
    if(!r.ok)throw 0; return r.text();
  }).then(function(t){
    var d=extractD(t); if(!d)throw 0;
    dCache[date]={date:date,D:d}; return dCache[date];
  }).catch(function(){return null})
}

/* ===== 합산 ===== */
function mergeBy(listOfLists,keyFn,sumKeys,keepKeys){
  var map={},order=[];
  listOfLists.forEach(function(arr){(arr||[]).forEach(function(r){
    var k=keyFn(r); if(k==null)return;
    var t=map[k];
    if(!t){t={};keepKeys.forEach(function(kk){t[kk]=r[kk]});sumKeys.forEach(function(sk){t[sk]=0});map[k]=t;order.push(k)}
    sumKeys.forEach(function(sk){t[sk]+=(r[sk]||0)})
  })});
  return order.map(function(k){return map[k]})
}
function sumObj(t,s,keys){keys.forEach(function(k){t[k]=(t[k]||0)+((s&&s[k])||0)})}
function deco(r){return Object.assign({},r,{_camps:[r.campaign],_grps:[r.adgroup],_pids:[r.pid],_split_count:1})}
function grpKey(name){
  try{if(typeof classify==='function')return classify(name)}catch(e){}
  return (name||'').split(' ')[0]||'기타'
}
function mergeD(list){
  var last=list[list.length-1].D;
  var M={};
  /* total + advoost */
  M.total={imp:0,clk:0,cost:0,count:0,advoost:{cost:0,imp:0,clk:0,rows:0}};
  list.forEach(function(x){
    sumObj(M.total,x.D.total,['imp','clk','cost']);
    sumObj(M.total.advoost,x.D.total&&x.D.total.advoost,['cost','imp','clk','rows']);
  });
  /* all_rows: 상품(소재) 단위 합산 */
  M.all_rows=mergeBy(list.map(function(x){return x.D.all_rows}),
    function(r){return r.pid||r.name},['imp','clk','cost'],
    ['campaign','adgroup','pid','name','url']);
  M.total.count=M.all_rows.length;
  M.top_cost=M.all_rows.slice().sort(function(a,b){return b.cost-a.cost}).slice(0,20).map(deco);
  M.top_click=M.all_rows.slice().sort(function(a,b){return b.clk-a.clk}).slice(0,20).map(deco);
  M.campaigns=mergeBy(list.map(function(x){return x.D.campaigns}),
    function(r){return r.name},['cost','clk','imp'],['name'])
    .sort(function(a,b){return b.cost-a.cost});
  /* 장바구니/구매 */
  var CONV_SUM=['buy_n','buy_v','d_buy_n','d_buy_v','i_buy_n','i_buy_v','cart_n','cart_v'];
  M.cart=mergeBy(list.map(function(x){return x.D.cart}),function(r){return r.pid||r.name},CONV_SUM,['pid','name','url','store'])
    .sort(function(a,b){return b.cart_v-a.cart_v});
  M.buy=mergeBy(list.map(function(x){return x.D.buy}),function(r){return r.pid||r.name},CONV_SUM,['pid','name','url','store'])
    .sort(function(a,b){return b.buy_v-a.buy_v});
  M.cart_total={n:0,v:0}; M.buy_total={n:0,v:0,d_n:0,d_v:0,i_n:0,i_v:0};
  list.forEach(function(x){
    sumObj(M.cart_total,x.D.cart_total,['n','v']);
    sumObj(M.buy_total,x.D.buy_total,['n','v','d_n','d_v','i_n','i_v']);
  });
  /* 비전환 그룹: 기간 합산 기준 재계산 (기간 중 구매 0 + 광고비 발생) */
  var buyPid={}; M.buy.forEach(function(r){if(r.buy_n>0){buyPid[r.pid||r.name]=1}});
  var gmap={};
  M.all_rows.forEach(function(r){
    var g=grpKey(r.name);
    if(!gmap[g])gmap[g]={name:g,cost:0,clk:0,imp:0,count:0,items:[],_conv:false};
    var t=gmap[g]; t.cost+=r.cost;t.clk+=r.clk;t.imp+=r.imp;t.count++;t.items.push(r);
    if(buyPid[r.pid||r.name])t._conv=true;
  });
  M.no_conv_groups=Object.keys(gmap).map(function(k){return gmap[k]})
    .filter(function(g){return !g._conv&&g.cost>0})
    .sort(function(a,b){return b.cost-a.cost})
    .map(function(g){return {name:g.name,cost:g.cost,clk:g.clk,imp:g.imp,count:g.count,
      items:g.items.sort(function(a,b){return b.cost-a.cost}).slice(0,10).map(deco)}});
  M.no_conv_total=M.no_conv_groups.reduce(function(s,g){return s+g.cost},0);
  /* 클릭했지만 구매없음: 일별 목록 합산 후 기간 중 구매된 상품 제외 */
  var buyName={}; M.buy.forEach(function(r){if(r.buy_n>0)buyName[r.name]=1});
  M.click_no_buy=mergeBy(list.map(function(x){return x.D.click_no_buy}),
    function(r){return r.name},['clk','cost','imp'],['name','url','camps','grps','pid_count','thumb'])
    .filter(function(r){return !buyName[r.name]})
    .sort(function(a,b){return b.cost-a.cost}).slice(0,20);
  M.click_no_buy_total={count:M.click_no_buy.length,
    clk_sum:M.click_no_buy.reduce(function(s,r){return s+r.clk},0),
    cost_sum:M.click_no_buy.reduce(function(s,r){return s+r.cost},0)};
  /* 파워링크(B) */
  var nb={total:{imp:0,clk:0,cost:0,count:0}};
  list.forEach(function(x){sumObj(nb.total,x.D.naver_b&&x.D.naver_b.total,['imp','clk','cost'])});
  nb.total.count=(last.naver_b&&last.naver_b.total&&last.naver_b.total.count)||0;
  nb.campaigns=mergeBy(list.map(function(x){return x.D.naver_b&&x.D.naver_b.campaigns}),
    function(r){return r.cid||r.name},['cost','clk','imp'],['name','cid'])
    .sort(function(a,b){return b.cost-a.cost});
  nb.adgroups=mergeBy(list.map(function(x){return x.D.naver_b&&x.D.naver_b.adgroups}),
    function(r){return (r.cid||'')+'|'+r.name},['cost','clk','imp'],['name','campaign','cid','headline','url'])
    .sort(function(a,b){return b.cost-a.cost});
  nb.active_per_camp=(last.naver_b&&last.naver_b.active_per_camp)||{};
  M.b_conv={n:0,v:0};
  list.forEach(function(x){sumObj(M.b_conv,x.D.b_conv,['n','v'])});
  nb.ctr=nb.total.imp?+(nb.total.clk/nb.total.imp*100).toFixed(2):0;
  nb.cpc=nb.total.clk?Math.round(nb.total.cost/nb.total.clk):0;
  nb.roas=nb.total.cost?+(M.b_conv.v/nb.total.cost*100).toFixed(1):0;
  M.naver_b=nb;
  /* 구글애즈(G) */
  var g={total:{cost:0,clk:0,imp:0,conv:0},buy_v:0,buy_n:0};
  list.forEach(function(x){
    var gd=x.D.google||{};
    sumObj(g.total,gd.total,['cost','clk','imp','conv']);
    g.buy_v+=gd.buy_v||0; g.buy_n+=gd.buy_n||0;
  });
  g.campaigns=mergeBy(list.map(function(x){return x.D.google&&x.D.google.campaigns}),
    function(r){return r.name},['cost','clk','imp','conv'],['name','url'])
    .sort(function(a,b){return b.cost-a.cost});
  g.devices={};
  list.forEach(function(x){
    var dv=(x.D.google&&x.D.google.devices)||{};
    Object.keys(dv).forEach(function(k){
      if(!g.devices[k])g.devices[k]={cost:0,clk:0};
      sumObj(g.devices[k],dv[k],['cost','clk']);
    });
  });
  g.search_terms=mergeBy(list.map(function(x){return x.D.google&&x.D.google.search_terms}),
    function(r){return r.term},['clk','cost','conv','imp'],
    ['term','adgroup','match_type','match_label','matched_kw','url','url_kw'])
    .sort(function(a,b){return b.cost-a.cost}).slice(0,10);
  g.trend=list.map(function(x){
    var t=(x.D.google&&x.D.google.total)||{};
    return {date:x.date,cost:t.cost||0,clk:t.clk||0,conv:t.conv||0};
  });
  g.keywords_top=mergeBy(list.map(function(x){return x.D.google&&x.D.google.keywords_top}),
    function(r){return r.text+'|'+(r.campaign||'')},['cost'],['text','url','campaign'])
    .sort(function(a,b){return b.cost-a.cost}).slice(0,20);
  g.fetch_ok=list.some(function(x){return x.D.google&&x.D.google.fetch_ok});
  g.ctr=g.total.imp?+(g.total.clk/g.total.imp*100).toFixed(2):0;
  g.cpc=g.total.clk?Math.round(g.total.cost/g.total.clk):0;
  g.roas=g.total.cost?+(g.buy_v/g.total.cost*100).toFixed(1):0;
  M.google=g;
  /* 디바이스/시간대(A) */
  M.device_a={};
  list.forEach(function(x){var dv=x.D.device_a||{};Object.keys(dv).forEach(function(k){
    if(!M.device_a[k])M.device_a[k]={imp:0,clk:0,cost:0};
    sumObj(M.device_a[k],dv[k],['imp','clk','cost']);
  })});
  M.hour_a={};
  list.forEach(function(x){var h=x.D.hour_a||{};Object.keys(h).forEach(function(k){
    if(!M.hour_a[k])M.hour_a[k]={imp:0,clk:0,cost:0};
    sumObj(M.hour_a[k],h[k],['imp','clk','cost']);
  })});
  /* 통합/리포트/메타 */
  M.combined={imp:M.total.imp+nb.total.imp+g.total.imp,
    clk:M.total.clk+nb.total.clk+g.total.clk,
    cost:M.total.cost+nb.total.cost+g.total.cost,
    buy_v:M.buy_total.v+M.b_conv.v+g.buy_v};
  M.combined.roas=M.combined.cost?+(M.combined.buy_v/M.combined.cost*100).toFixed(1):0;
  nb.share_pct=M.combined.cost?+(nb.total.cost/M.combined.cost*100).toFixed(1):0;
  M.report={top_revenue:M.buy.slice(0,5),
    no_conv_cost:M.no_conv_total,
    no_conv_pct:M.total.cost?+(M.no_conv_total/M.total.cost*100).toFixed(1):0,
    no_conv_count:M.no_conv_groups.length,
    direct_pct:M.buy_total.v?+(M.buy_total.d_v/M.buy_total.v*100).toFixed(1):0,
    indirect_pct:M.buy_total.v?+(M.buy_total.i_v/M.buy_total.v*100).toFixed(1):0};
  M.meta={date:last.meta.date,weekday:last.meta.weekday,generated_at:last.meta.generated_at,
    roas:M.total.cost?+(M.buy_total.v/M.total.cost*100).toFixed(1):0,
    cart_roas:M.total.cost?+((M.buy_total.v+M.cart_total.v)/M.total.cost*100).toFixed(1):0,
    no_conv_cost:M.report.no_conv_cost,no_conv_pct:M.report.no_conv_pct,no_conv_count:M.report.no_conv_count};
  return M;
}

/* ===== 오버레이 (일일 페이지에서만) ===== */
var overlay=null;
function paggClose(){
  if(overlay){overlay.remove();overlay=null}
  var chips=document.querySelectorAll('#paggBtns button');
  for(var i=0;i<chips.length;i++)chips[i].classList.toggle('on',chips[i].dataset.k==='today');
}
function paggOpen(key){
  var cur=anchor(); if(!cur)return;
  var r=range(key,cur), s=r[0], e=r[1];
  if(!overlay){
    overlay=document.createElement('div');overlay.id='paggOverlay';
    document.body.appendChild(overlay);
  }
  overlay.innerHTML='<div class="pagg-load">기간 합산 준비 중…</div>';
  var chips=document.querySelectorAll('#paggBtns button');
  for(var i=0;i<chips.length;i++)chips[i].classList.toggle('on',chips[i].dataset.k===key);
  /* 날짜 목록 */
  var dates=[],d=parseD(s),end=parseD(e);
  while(d<=end){dates.push(fmtD(d));d.setDate(d.getDate()+1)}
  var done=0,results=[];
  var loadEl=overlay.firstChild;
  function tick(){done++;loadEl.textContent='기간 데이터 로딩 '+done+'/'+dates.length+'일…'}
  /* 동시 8개 제한 */
  var idx=0;
  function next(){
    if(idx>=dates.length)return Promise.resolve();
    var my=dates[idx++];
    return fetchDay(my).then(function(x){if(x)results.push(x);tick();return next()})
  }
  var lanes=[];for(var L=0;L<8;L++)lanes.push(next());
  Promise.all(lanes).then(function(){
    results.sort(function(a,b){return a.date<b.date?-1:1});
    if(!results.length){
      overlay.innerHTML='<div class="pagg-load">'+label(key)+' ('+s+' ~ '+e+') 구간에 보고서가 없습니다.'+
        '<br><button class="pagg-x" onclick="__paggClose()">닫기</button></div>';
      return;
    }
    var M=mergeD(results);
    loadEl.textContent='합산 렌더링 중…';
    fetch(location.pathname.split('/').pop()||'latest.html').then(function(rr){return rr.text()}).then(function(html){
      var i=html.indexOf('const D =');
      var j=html.indexOf('\n',i);
      var seg=html.slice(i,j);
      var a=seg.indexOf('{'), b=seg.lastIndexOf('}');
      var st={key:key,label:label(key),s:s,e:e,days:results.length};
      var newHtml=html.slice(0,i+a)+JSON.stringify(M)+html.slice(i+b+1);
      newHtml=newHtml.replace('</head>','<script>window.__PAGG='+JSON.stringify(st)+';<\/script></head>');
      var ifr=document.createElement('iframe');ifr.className='pagg-frame';
      overlay.appendChild(ifr);
      ifr.srcdoc=newHtml;
      ifr.onload=function(){if(loadEl.parentNode)loadEl.remove()};
    });
  });
}
window.__paggOpen=paggOpen;
window.__paggClose=paggClose;

/* ===== 버튼/스타일 ===== */
function init(){
  var dateBox=document.querySelector('.date.dn-inline')||document.getElementById('dateNav');
  if(!dateBox){if(tries++<40){setTimeout(init,50)}return}
  var css=document.createElement('style');
  css.textContent='#paggBtns{display:flex;gap:5px;justify-content:flex-end;margin-top:8px;flex-wrap:wrap;position:relative;z-index:3}'+
   '#paggBtns button{background:rgba(255,255,255,.05);border:1px solid var(--line,#252b3d);color:var(--sub,#aab3c5);font-size:11px;padding:4px 10px;border-radius:14px;cursor:pointer;transition:.15s}'+
   '#paggBtns button:hover{border-color:var(--blue,#3b82f6);color:#fff}'+
   '#paggBtns button.on{background:var(--blue,#3b82f6);border-color:var(--blue,#3b82f6);color:#fff;font-weight:700}'+
   '#paggOverlay{position:fixed;inset:0;z-index:99999;background:var(--bg,#0b0e17);display:flex;flex-direction:column}'+
   '#paggOverlay .pagg-load{margin:auto;color:#fff;font-size:15px;text-align:center;line-height:2}'+
   '#paggOverlay .pagg-x{display:inline-block;margin-top:10px;background:var(--blue,#3b82f6);border:0;color:#fff;padding:6px 18px;border-radius:8px;cursor:pointer;font-size:13px}'+
   '#paggOverlay .pagg-frame{flex:1;width:100%;border:0}';
  document.head.appendChild(css);
  var bar=document.createElement('div');bar.id='paggBtns';
  BTNS.forEach(function(b){
    var btn=document.createElement('button');btn.textContent=b[1];btn.dataset.k=b[0];
    if(IN_AGG){
      if(window.__PAGG.key===b[0])btn.classList.add('on');
      btn.onclick=function(){
        if(b[0]==='today'){window.parent.__paggClose()}
        else if(window.__PAGG.key!==b[0]){window.parent.__paggOpen(b[0])}
      };
    }else{
      if(b[0]==='today')btn.classList.add('on');
      btn.onclick=function(){
        if(b[0]==='today'){paggClose()}
        else{paggOpen(b[0])}
      };
    }
    bar.appendChild(btn);
  });
  if(dateBox.id==='dateNav'){dateBox.parentElement.insertBefore(bar,dateBox.nextSibling)}
  else{dateBox.parentElement.appendChild(bar)}
  /* 합산 화면(iframe 내부): 날짜 내비를 기간 라벨로 고정 */
  if(IN_AGG){
    var st=window.__PAGG;
    var lbl=document.getElementById('dnLabel');
    if(lbl)lbl.textContent=st.label+' 합산 · '+st.s+' ~ '+st.e+' · '+st.days+'일';
    var pv=document.getElementById('dnPrev'),nx=document.getElementById('dnNext'),pk=document.getElementById('dnPick');
    if(pv)pv.style.display='none'; if(nx)nx.style.display='none';
    if(pk)pk.disabled=true;
    var pill=document.querySelector('.dn-date');
    if(pill){pill.style.pointerEvents='none';pill.style.borderColor='var(--blue,#3b82f6)'}
    document.addEventListener('keydown',function(ev){if(ev.key==='Escape')window.parent.__paggClose()});
  }else{
    document.addEventListener('keydown',function(ev){if(ev.key==='Escape')paggClose()});
  }
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init)}
else{init()}
})();
