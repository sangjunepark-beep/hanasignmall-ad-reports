/* period-agg: 날짜 내비 하단 기간별 집계 버튼 (1주일/저번달/이번달/1개월/3개월/1년)
   데이터: ceo-report/daily-kpi.json (build_report.py가 매일 누적) — 네이버 검색광고 기준 */
(function(){
var BTNS=[['w1','1주일'],['lastm','저번달'],['thism','이번달'],['m1','1개월'],['m3','3개월'],['y1','1년']];
var cache=null, active=null, tries=0;
function pad(n){return(n<10?'0':'')+n}
function fmt(n){return (Math.round(n)+'').replace(/\B(?=(\d{3})+(?!\d))/g,',')}
function fmtD(d){return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())}
function parse(s){var p=s.split('-');return new Date(+p[0],+p[1]-1,+p[2])}
function anchor(){
  var el=document.getElementById('dnLabel');
  var m=el&&el.textContent.match(/(\d{4}-\d{2}-\d{2})/);
  if(m)return m[1];
  m=document.title.match(/(\d{4}-\d{2}-\d{2})/); if(m)return m[1];
  m=location.pathname.match(/(\d{4}-\d{2}-\d{2})\.html/); return m?m[1]:null;
}
function range(key,cur){
  var d=parse(cur),s,e;
  if(key==='w1'){s=new Date(d);s.setDate(s.getDate()-6);e=d}
  else if(key==='lastm'){s=new Date(d.getFullYear(),d.getMonth()-1,1);e=new Date(d.getFullYear(),d.getMonth(),0)}
  else if(key==='thism'){s=new Date(d.getFullYear(),d.getMonth(),1);e=d}
  else if(key==='m1'){s=new Date(d);s.setDate(s.getDate()-29);e=d}
  else if(key==='m3'){s=new Date(d);s.setDate(s.getDate()-89);e=d}
  else{s=new Date(d);s.setDate(s.getDate()-364);e=d}
  return [fmtD(s),fmtD(e)]
}
function load(cb){
  if(cache){cb(cache);return}
  fetch('daily-kpi.json').then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){cache=j;cb(j)})
  .catch(function(){
    var p=document.getElementById('paggPanel');
    if(p){p.style.display='block';p.innerHTML='<div class="pagg-empty">기간 집계 데이터(daily-kpi.json)를 불러오지 못했습니다.</div>'}
  })
}
function render(key,label){
  var cur=anchor(); if(!cur)return;
  load(function(data){
    var r=range(key,cur), s=r[0], e=r[1];
    var rows=data.filter(function(x){return x.date>=s&&x.date<=e});
    var panel=document.getElementById('paggPanel');
    panel.style.display='block';
    if(!rows.length){
      panel.innerHTML='<div class="pagg-empty">'+label+' ('+s+' ~ '+e+') 구간에 데이터가 없습니다. 데이터 시작일: '+(data[0]?data[0].date:'-')+'</div>';
      return;
    }
    var t={imp:0,clk:0,cost:0,cart_n:0,cart_v:0,buy_n:0,buy_v:0};
    rows.forEach(function(x){for(var k in t)t[k]+=(x.a&&x.a[k])||0});
    var ctr=t.imp?(t.clk/t.imp*100).toFixed(2)+'%':'-';
    var cpc=t.clk?fmt(t.cost/t.clk)+'원':'-';
    var roas=t.cost?(t.buy_v/t.cost*100).toFixed(1):'-';
    panel.innerHTML=
      '<div class="pagg-head"><b>기간별 집계 — '+label+'</b><span>'+s+' ~ '+e+' · 집계 '+rows.length+'일 · 네이버 검색광고 기준</span></div>'+
      '<div class="kpi" style="margin-bottom:0">'+
      '<div class="card"><div class="label">노출</div><div class="val">'+fmt(t.imp)+'</div><div class="sub">건</div></div>'+
      '<div class="card click"><div class="label">클릭</div><div class="val">'+fmt(t.clk)+'</div><div class="sub">CTR '+ctr+'</div></div>'+
      '<div class="card cost"><div class="label">광고비</div><div class="val">'+fmt(t.cost)+'<span class="unit">원</span></div><div class="sub">CPC '+cpc+'</div></div>'+
      '<div class="card cart"><div class="label">장바구니</div><div class="val">'+fmt(t.cart_n)+'</div><div class="sub">'+fmt(t.cart_v)+' 원</div></div>'+
      '<div class="card buy"><div class="label">구매전환</div><div class="val">'+fmt(t.buy_n)+'</div><div class="sub">'+fmt(t.buy_v)+' 원</div></div>'+
      '<div class="card roas"><div class="label">ROAS</div><div class="val">'+roas+'<span class="unit">%</span></div><div class="sub">광고비 '+fmt(t.cost)+' → 매출 '+fmt(t.buy_v)+'</div></div>'+
      '</div>';
  })
}
function init(){
  var dateBox=document.querySelector('.date.dn-inline')||document.getElementById('dateNav');
  if(!dateBox){if(tries++<40){setTimeout(init,50)}return}
  var css=document.createElement('style');
  css.textContent='#paggBtns{display:flex;gap:5px;justify-content:flex-end;margin-top:8px;flex-wrap:wrap;position:relative;z-index:3}'+
   '#paggBtns button{background:rgba(255,255,255,.05);border:1px solid var(--line,#252b3d);color:var(--sub,#aab3c5);font-size:11px;padding:4px 10px;border-radius:14px;cursor:pointer;transition:.15s}'+
   '#paggBtns button:hover{border-color:var(--blue,#3b82f6);color:#fff}'+
   '#paggBtns button.on{background:var(--blue,#3b82f6);border-color:var(--blue,#3b82f6);color:#fff;font-weight:700}'+
   '#paggPanel{display:none;background:var(--card,#141927);border:1px solid var(--blue,#3b82f6);border-radius:12px;padding:14px 16px;margin:0 0 18px}'+
   '#paggPanel .pagg-head{display:flex;align-items:baseline;gap:10px;margin-bottom:12px;flex-wrap:wrap}'+
   '#paggPanel .pagg-head b{font-size:14px;color:#fff}'+
   '#paggPanel .pagg-head span{font-size:11px;color:var(--muted,#6b7488)}'+
   '#paggPanel .pagg-empty{font-size:12px;color:var(--muted,#6b7488)}';
  document.head.appendChild(css);
  var bar=document.createElement('div');bar.id='paggBtns';
  BTNS.forEach(function(b){
    var btn=document.createElement('button');btn.textContent=b[1];
    btn.onclick=function(){
      var panel=document.getElementById('paggPanel');
      if(active===b[0]){active=null;panel.style.display='none';this.classList.remove('on');return}
      active=b[0];
      var sib=document.querySelectorAll('#paggBtns button');
      for(var i=0;i<sib.length;i++)sib[i].classList.remove('on');
      this.classList.add('on');
      render(b[0],b[1]);
    };
    bar.appendChild(btn);
  });
  if(dateBox.id==='dateNav'){dateBox.parentElement.insertBefore(bar,dateBox.nextSibling)}
  else{dateBox.parentElement.appendChild(bar)}
  var panel=document.createElement('div');panel.id='paggPanel';
  var head=document.querySelector('.head');
  if(head){head.parentElement.insertBefore(panel,head.nextSibling)}
  else{dateBox.parentElement.insertBefore(panel,bar.nextSibling)}
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init)}
else{init()}
})();
