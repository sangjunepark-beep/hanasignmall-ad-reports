import pickle, json, html, os, sys
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, '/tmp')
from keyword_func import extract_keyword

S = pickle.load(open('/tmp/agg_state.pkl','rb'))
pid_name = S['pid_name']; pid_url = S['pid_url']; pid_store = S['pid_store']
SS = pickle.load(open('/tmp/sales_state.pkl','rb'))
SALES_ROWS = SS['rows_data']

WEEKS = [
    ('1주차', '5/1 ~ 5/8', 4, ['2026-05-01','2026-05-04','2026-05-06','2026-05-07','2026-05-08']),
    ('2주차', '5/11 ~ 5/15', 5, ['2026-05-11','2026-05-12','2026-05-13','2026-05-14','2026-05-15']),
    ('3주차', '5/18 ~ 5/22', 5, ['2026-05-18','2026-05-19','2026-05-20','2026-05-21','2026-05-22']),
    ('4주차', '5/25 ~ 5/27', 2, ['2026-05-26','2026-05-27']),
]
ALL_DAYS = sorted({d for _,_,_,ds in WEEKS for d in ds})
WEEKS_ALL = WEEKS + [('전체', '5/1 ~ 5/27 영업일', 16, ALL_DAYS)]

CHANNEL_GROUPS = {
    'CS': ['CS'],
    '영업': ['영업'],
    '스마트스토어': ['스마트스토어','네이버페이','하나몰','더바른사인','로켓출력공장'],
    '자사몰': ['고도몰5','신규몰'],
    '오픈마켓': ['쿠팡(신)','G마켓','11번가','옥션'],
}


# 공휴일 매핑 (2026년 5월)
HOLIDAYS = {
    '1주차': '5/1 (금) 근로자의날 · 5/5 (화) 어린이날 휴무',
    '4주차': '5/25 (월) 부처님오신날 대체공휴일 휴무',
}

def fmt(n): return f'{n:,}' if n else '0'
def fmt_won(n):
    if not n: return '0원'
    if n >= 100_000_000: return f'{n/100_000_000:.2f}억'
    if n >= 10_000_000: return f'{n/10_000_000:.1f}천만'
    if n >= 10_000: return f'{n/10_000:.0f}만'
    return f'{int(n):,}'
def fmt_won_full(n): return f'{int(n):,}원' if n else '0원'

# 광고 집계
def agg_ad(days):
    t = {'clk':0,'imp':0,'cost':0,'cart_n':0,'cart_v':0,
         'd_buy_n':0,'d_buy_v':0,'i_buy_n':0,'i_buy_v':0,'pids':set()}
    for d in days:
        for pid, v in S['per_day_pid_clk'].get(d, {}).items():
            t['clk'] += v; t['pids'].add(pid)
        for pid, v in S['per_day_pid_imp'].get(d, {}).items(): t['imp'] += v
        for pid, v in S['per_day_pid_cost'].get(d, {}).items(): t['cost'] += v
        for pid, v in S['per_day_pid_cart_n'].get(d, {}).items(): t['cart_n'] += v
        for pid, v in S['per_day_pid_cart_v'].get(d, {}).items(): t['cart_v'] += v
        for pid, v in S['per_day_pid_d_buy_n'].get(d, {}).items(): t['d_buy_n'] += v
        for pid, v in S['per_day_pid_d_buy_v'].get(d, {}).items(): t['d_buy_v'] += v
        for pid, v in S['per_day_pid_i_buy_n'].get(d, {}).items(): t['i_buy_n'] += v
        for pid, v in S['per_day_pid_i_buy_v'].get(d, {}).items(): t['i_buy_v'] += v
    t['pids'] = len(t['pids'])
    t['buy_n'] = t['d_buy_n'] + t['i_buy_n']
    t['buy_v'] = t['d_buy_v'] + t['i_buy_v']
    return t

# 매출 집계
def agg_sales(days):
    by_ch = defaultdict(lambda: {'cnt':0, 'amt':0})
    by_kw_ch = defaultdict(lambda: defaultdict(lambda: {'cnt':0, 'amt':0}))
    total = {'cnt':0, 'amt':0}
    day_set = set(days)
    for d, week, cat, kw, qty, amt, name in SALES_ROWS:
        if d not in day_set: continue
        if not isinstance(amt, (int, float)): continue
        by_ch[cat]['cnt'] += 1; by_ch[cat]['amt'] += amt
        by_kw_ch[cat][kw]['cnt'] += 1; by_kw_ch[cat][kw]['amt'] += amt
        total['cnt'] += 1; total['amt'] += amt
    return by_ch, by_kw_ch, total

def sum_group(by_ch, group_names):
    t = {'cnt':0, 'amt':0}
    for n in group_names:
        v = by_ch.get(n, {'cnt':0,'amt':0})
        t['cnt'] += v['cnt']; t['amt'] += v['amt']
    return t

# 채널 그룹 합산 키워드 (자사몰=하나몰+고도몰5+신규몰... 등 합산)
def group_kw_agg(by_kw_ch, group_names):
    merged = defaultdict(lambda: {'cnt':0, 'amt':0})
    for ch in group_names:
        for kw, v in by_kw_ch.get(ch, {}).items():
            merged[kw]['cnt'] += v['cnt']
            merged[kw]['amt'] += v['amt']
    return merged

# 광고 클릭을 키워드로 묶기 (pid → name → extract_keyword)
def agg_ad_kw(days):
    kw_clk = defaultdict(int)
    kw_cost = defaultdict(int)
    for d in days:
        for pid, clk in S['per_day_pid_clk'].get(d, {}).items():
            name = pid_name.get(pid, '')
            kw = extract_keyword(name) if name and not name.startswith('nad-') else f'상품 #{("".join(c for c in pid if c.isdigit()))[-9:] or "미확인"}'
            if not kw: kw = '(기타)'
            kw_clk[kw] += clk
        for pid, cost in S['per_day_pid_cost'].get(d, {}).items():
            name = pid_name.get(pid, '')
            kw = extract_keyword(name) if name and not name.startswith('nad-') else f'상품 #{("".join(c for c in pid if c.isdigit()))[-9:] or "미확인"}'
            if not kw: kw = '(기타)'
            kw_cost[kw] += cost
    return kw_clk, kw_cost

period_data = {}
POPUP_DATA = {}  # JS에 임베드

for name, range_str, days_n, days in WEEKS_ALL:
    ad = agg_ad(days)
    sales_by_ch, sales_by_kw_ch, sales_total = agg_sales(days)
    
    # 광고 키워드 (클릭)
    kw_clk, kw_cost = agg_ad_kw(days)
    ad_kw_top = sorted(kw_clk.items(), key=lambda x: -x[1])[:30]
    
    # 매출 키워드 (채널 그룹별)
    sales_kw_top_by_group = {}
    for gname, members in CHANNEL_GROUPS.items():
        merged = group_kw_agg(sales_by_kw_ch, members)
        top = sorted(merged.items(), key=lambda x: -x[1]['amt'])[:30]
        sales_kw_top_by_group[gname] = [[k, v['cnt'], v['amt']] for k, v in top]
    
    # 전체 매출 키워드 (모든 채널 합산)
    all_merged = defaultdict(lambda: {'cnt':0, 'amt':0})
    for ch_kw in sales_by_kw_ch.values():
        for kw, v in ch_kw.items():
            all_merged[kw]['cnt'] += v['cnt']
            all_merged[kw]['amt'] += v['amt']
    all_top = sorted(all_merged.items(), key=lambda x: -x[1]['amt'])[:30]
    sales_kw_top_by_group['전체'] = [[k, v['cnt'], v['amt']] for k, v in all_top]
    
    period_data[name] = {
        'range': range_str, 'days_n': days_n,
        'ad': ad, 'sales_by_ch': sales_by_ch, 'sales_total': sales_total,
    }
    
    POPUP_DATA[name] = {
        'range': range_str,
        'ad_click': [[k, v] for k, v in ad_kw_top],
        'sales': sales_kw_top_by_group,
    }

now_str = datetime.now().strftime('%Y년 %m월 %d일 %H:%M')
print('데이터 준비 완료. 키워드 개수 샘플:')
for name in ['1주차','전체']:
    print(f"  [{name}]")
    print(f"    광고 클릭 키워드: {len(POPUP_DATA[name]['ad_click'])}개")
    for g in CHANNEL_GROUPS:
        print(f"    매출[{g}] 키워드: {len(POPUP_DATA[name]['sales'][g])}개")

buf = []
w = buf.append

# CSS / Header / 섹션 1 (week-cards) — v5 그대로 가져옴
w(f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>하나사인몰 — 주간·월간 종합 비교 (대화형)</title>
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.min.css">
<style>
  :root {{
    --bg: #0a0e1a; --bg-2: #131a2b; --bg-3: #1a2238;
    --border: #2d3a58; --border-light: #3d4a6b;
    --text: #f1f5f9; --text-muted: #94a3b8; --text-dim: #64748b;
    --green: #03c75a; --green-bg: rgba(3,199,90,0.1); --green-dim: #028a3f;
    --orange: #fb923c; --orange-bg: rgba(251,146,60,0.12); --orange-dim: #c2470a;
    --gold: #facc15; --gold-bg: rgba(250,204,21,0.08);
    --link: #93c5fd;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin:0; padding:0; }}
  body {{
    font-family: 'Pretendard', -apple-system, sans-serif;
    background: var(--bg); color: var(--text);
    font-size: 16px; line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{ max-width: 1500px; margin: 0 auto; padding: 56px 28px 100px; }}
  .header {{ margin-bottom: 56px; padding-bottom: 32px; border-bottom: 1px solid var(--border); }}
  h1 {{ font-size: 42px; font-weight: 800; margin: 0 0 14px; letter-spacing: -1px; }}
  h1 .accent {{ background: linear-gradient(90deg, var(--green), var(--orange));
    -webkit-background-clip: text; background-clip: text; color: transparent; }}
  .meta {{ color: var(--text-muted); font-size: 16px; margin-top: 8px; }}
  .meta-item {{ display: inline-block; margin-right: 24px; }}
  .meta-item b {{ color: var(--text); font-weight: 600; }}
  .notice {{ background: var(--gold-bg); border-left: 4px solid var(--gold);
    padding: 18px 22px; border-radius: 10px; margin: 32px 0;
    font-size: 15px; color: #fde68a; line-height: 1.65; }}
  .notice .hint {{ display: block; margin-top: 8px; color: #fef9c3; font-weight: 600; }}
  .notice .hint kbd {{ background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px;
    font-family: 'Pretendard'; font-size: 13px; }}

  section {{ margin-top: 72px; }}
  h2 {{ font-size: 28px; font-weight: 700; margin: 0 0 24px;
    display: flex; align-items: center; gap: 14px; letter-spacing: -0.5px; }}
  h2 .num {{ display: inline-flex; align-items: center; justify-content: center;
    width: 38px; height: 38px; background: var(--green); color: #021c0f;
    border-radius: 10px; font-size: 20px; font-weight: 800; }}
  h2 .sub {{ font-size: 15px; color: var(--text-muted); font-weight: 500; }}

  /* 주차 카드 (v5 그대로) */
  .week-cards {{ display:grid; grid-template-columns: repeat(5, 1fr); gap: 14px; }}
  .week-card {{ background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 14px; padding: 20px; transition: all 0.2s; }}
  .week-card:hover {{ border-color: var(--green); transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(3,199,90,0.1); }}
  .week-card.all {{ border-color: var(--green-dim); background: linear-gradient(180deg, var(--bg-2), rgba(3,199,90,0.04)); }}
  .week-head {{ margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }}
  .week-head .name {{ font-size: 18px; font-weight: 800; color: var(--text); }}
  .week-head .range {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
  .week-head .holiday {{ display: block; margin-top: 6px; font-size: 12px; font-weight: 700;
    color: #f87171; line-height: 1.3; }}
  .week-head .holiday::before {{ content: '● '; color: #ef4444; }}
  .sec-block {{ margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px dashed var(--border); }}
  .sec-block:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
  .sec-block .label {{ font-size: 11px; color: var(--text-dim); font-weight: 700;
    letter-spacing: 0.5px; margin-bottom: 8px;
    display: flex; align-items: center; gap: 6px; }}
  .sec-block.ad .label {{ color: var(--green); }}
  .sec-block.sales .label {{ color: var(--orange); }}
  .sec-block .label .dot {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; }}
  .big-num {{ font-size: 22px; font-weight: 800; line-height: 1.1;
    font-variant-numeric: tabular-nums; letter-spacing: -0.5px; margin-bottom: 4px; }}
  .sec-block.ad .big-num {{ color: var(--green); }}
  .sec-block.sales .big-num {{ color: var(--orange); }}
  .big-num small {{ font-size: 12px; color: var(--text-muted); font-weight: 500; margin-left: 4px; }}
  .stat-row {{ display:flex; justify-content:space-between; margin-top: 4px;
    font-size: 13px; color: var(--text-muted); }}
  .stat-row b {{ color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; font-size: 13.5px; }}
  .ch-bar {{ margin-top: 8px; }}
  .ch-bar-row {{ display: flex; align-items: center; gap: 6px;
    margin-bottom: 4px; font-size: 12px; }}
  .ch-bar-row .ch {{ width: 60px; color: var(--text-muted); font-weight: 600; flex-shrink: 0; }}
  .ch-bar-row .bar-wrap {{ flex: 1; height: 6px; background: var(--bg); border-radius: 3px; overflow: hidden; }}
  .ch-bar-row .bar {{ height: 100%; background: var(--orange); border-radius: 3px; }}
  .ch-bar-row .val {{ color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums;
    font-size: 12px; min-width: 60px; text-align: right; }}

  /* 통합 비교 표 — 클릭 가능 셀 강조 */
  .compare-wrap {{ background: var(--bg-2); border: 1px solid var(--border);
    border-radius: 14px; overflow: auto; }}
  .compare-table {{ width: 100%; border-collapse: separate; border-spacing: 0;
    font-size: 14.5px; min-width: 1000px; }}
  .compare-table thead tr.group th {{
    background: var(--bg-3); padding: 10px 12px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
    text-align: center; border-bottom: 1px solid var(--border); border-right: 1px solid var(--border); }}
  .compare-table thead .group .g-ad {{ color: var(--green); }}
  .compare-table thead .group .g-sales {{ color: var(--orange); }}
  .compare-table thead tr.cols th {{
    background: var(--bg-3); color: var(--text-muted); font-weight: 600;
    padding: 12px 14px; font-size: 12px;
    border-bottom: 2px solid var(--border); white-space: nowrap; }}
  .compare-table thead .r {{ text-align: right; }}
  .compare-table td {{ padding: 16px 14px;
    border-bottom: 1px solid var(--border);
    font-variant-numeric: tabular-nums; font-size: 15px; white-space: nowrap; }}
  .compare-table tbody tr:last-child td {{ border-bottom: none; }}
  .compare-table tbody tr.total-row {{ background: linear-gradient(90deg, var(--green-bg), var(--orange-bg)); }}
  .compare-table tbody tr.total-row td {{ font-weight: 700; }}
  .compare-table .r {{ text-align: right; }}
  .compare-table .period-name {{ font-weight: 700; font-size: 16px; }}
  .compare-table .div-strong {{ border-right: 2px solid var(--border-light); }}

  /* 클릭 가능 셀 */
  .clk-cell {{ cursor: pointer; position: relative; transition: background 0.15s; }}
  .clk-cell.ad-cell {{ color: var(--green); }}
  .clk-cell.sales-cell {{ color: var(--orange); }}
  .clk-cell:hover {{ background: rgba(255,255,255,0.06); }}
  .clk-cell::after {{ content: '↗'; position: absolute; top: 4px; right: 4px;
    font-size: 9px; color: var(--text-dim); opacity: 0.6; }}
  .clk-cell:hover::after {{ opacity: 1; color: var(--text); }}

  /* 팝업 */
  .popup {{ position: fixed; background: var(--bg-2);
    border: 1px solid var(--border-light); border-radius: 12px;
    width: 380px; max-height: 75vh; box-shadow: 0 12px 32px rgba(0,0,0,0.5);
    z-index: 1000; overflow: hidden;
    display: flex; flex-direction: column;
    animation: popup-in 0.18s ease-out; }}
  @keyframes popup-in {{
    from {{ opacity: 0; transform: translateY(-8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .popup-head {{ background: var(--bg-3); padding: 12px 14px;
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    cursor: move; user-select: none;
    flex-shrink: 0; }}
  .popup-head.ad {{ border-bottom-color: var(--green-dim); }}
  .popup-head.sales {{ border-bottom-color: var(--orange-dim); }}
  .popup-head .title {{ font-size: 14px; font-weight: 700; line-height: 1.3; }}
  .popup-head .title .week {{ color: var(--text-muted); font-weight: 500; font-size: 12px; display: block; margin-top: 2px; }}
  .popup-head .title .badge {{ display: inline-block; padding: 2px 8px;
    border-radius: 4px; font-size: 11px; font-weight: 700;
    margin-right: 6px; vertical-align: middle; }}
  .popup-head.ad .title .badge {{ background: var(--green-bg); color: var(--green); }}
  .popup-head.sales .title .badge {{ background: var(--orange-bg); color: var(--orange); }}
  .popup-close {{ width: 24px; height: 24px; border-radius: 6px;
    background: transparent; border: none; cursor: pointer;
    color: var(--text-muted); font-size: 18px; line-height: 1;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s; flex-shrink: 0; }}
  .popup-close:hover {{ background: var(--bg); color: var(--text); }}
  .popup-body {{ overflow-y: auto; padding: 6px 0; flex: 1; min-height: 0; }}
  .popup-body table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .popup-body th {{ padding: 8px 14px; text-align: left;
    color: var(--text-dim); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.4px; border-bottom: 1px solid var(--border);
    position: sticky; top: 0; background: var(--bg-2); }}
  .popup-body td {{ padding: 9px 14px; border-bottom: 1px solid var(--border);
    vertical-align: top; }}
  .popup-body tr:last-child td {{ border-bottom: none; }}
  .popup-body .rank {{ color: var(--text-dim); font-weight: 700;
    text-align: right; width: 22px; font-size: 12px; }}
  .popup-body .kw {{ color: var(--text); font-weight: 600; font-size: 13px; }}
  .popup-body .num {{ text-align: right; font-variant-numeric: tabular-nums;
    font-weight: 700; color: var(--text); white-space: nowrap; font-size: 13px; }}
  .popup-body .amt {{ color: var(--orange); font-size: 12px; font-weight: 700; }}
  .popup-body .ad-num {{ color: var(--green); }}

  
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .tab-body {{ padding: 32px 28px; }}
  .tab-info {{ color: var(--text-muted); font-size: 16px; margin-bottom: 28px;
    padding-bottom: 20px; border-bottom: 1px solid var(--border); }}
  .tab-info b {{ color: var(--green); font-weight: 700; }}
  .top-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 36px; }}
  .top-section + .top-section {{ margin-top: 36px; }}
  .top-title {{ font-size: 18px; font-weight: 700; color: var(--green);
    margin: 0 0 14px; padding-bottom: 12px; border-bottom: 2px solid var(--green-dim);
    display:flex; justify-content: space-between; align-items: baseline; }}
  .top-title .sub {{ color: var(--text-muted); font-size: 13px; font-weight: 500; }}
  .top-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  .top-table th {{ text-align: left; padding: 10px 8px 12px; color: var(--text-dim);
    font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--border); }}
  .top-table td {{ padding: 14px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  .top-table tbody tr:last-child td {{ border-bottom: none; }}
  .top-table tbody tr:hover {{ background: var(--bg-3); }}
  .top-table .rank {{ color: var(--text-dim); font-weight: 700; width: 28px;
    text-align: right; padding-right: 6px; font-variant-numeric: tabular-nums; font-size: 13px; }}
  .top-table .num {{ text-align: right; font-variant-numeric: tabular-nums;
    color: var(--text); font-weight: 700; white-space: nowrap; font-size: 15px; }}
  .top-table .amt {{ color: var(--text-dim); font-size: 13px; font-weight: 600; }}
  .pname .kw {{ font-size: 15px; font-weight: 700; color: var(--text); line-height: 1.4; }}
  .pname .kw a {{ color: var(--text); text-decoration: none; }}
  .pname .kw a:hover {{ color: var(--link); text-decoration: underline; }}
  .pname .full {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; line-height: 1.45; opacity: 0.85; }}
  .store-tag {{ display:inline-block; padding: 2px 8px; background: var(--bg);
    color: var(--text-muted); border-radius: 4px;
    font-size: 11px; font-weight: 700; margin-right: 8px;
    vertical-align: middle; border: 1px solid var(--border); }}

  footer {{ margin-top: 80px; padding-top: 32px; border-top: 1px solid var(--border);
    color: var(--text-dim); font-size: 13px; text-align: center; }}

  @media (max-width: 1200px) {{
    .week-cards {{ grid-template-columns: repeat(2, 1fr); }}
    h1 {{ font-size: 32px; }}
    h2 {{ font-size: 22px; }}
  }}
  @media (max-width: 640px) {{
    body {{ font-size: 15px; }}
    .container {{ padding: 32px 16px 60px; }}
    h1 {{ font-size: 26px; }}
    h2 {{ font-size: 19px; }}
    .week-cards {{ grid-template-columns: 1fr; gap: 14px; }}
    .compare-table th, .compare-table td {{ padding: 12px 10px; font-size: 13px; }}
    .popup {{ width: calc(100vw - 32px); }}
  }}
</style>
</head><body>
<div class="container">

<header class="header">
  <h1>주간 · 월간 <span class="accent">광고 ↔ 매출 비교</span></h1>
  <div class="meta">
    <span class="meta-item">생성 <b>{now_str}</b></span>
    <span class="meta-item">데이터 기간 <b>5월 1일 ~ 5월 27일 (영업일 16일, 공휴일 5/1·5/5·5/25 제외)</b></span>
  </div>
  <div class="meta" style="margin-top:14px">
    광고 <b style="color:var(--green)">●</b> 네이버 검색광고 · 매출 <b style="color:var(--orange)">●</b> CS · 영업 · 스마트스토어 · 자사몰 · 오픈마켓
  </div>
</header>



""")

# 섹션 1: 주차별 통합 카드 (v5와 동일)
max_ch_amt = 0
for name, _, _, _ in WEEKS_ALL:
    sale = period_data[name]['sales_by_ch']
    for gname, members in CHANNEL_GROUPS.items():
        v = sum_group(sale, members)['amt']
        if v > max_ch_amt: max_ch_amt = v

w('<section><h2><span class="num">1</span>주차별 한눈에 <span class="sub">· 광고 활동 + 실제 매출</span></h2>')
w('<div class="week-cards">')
for name, range_str, days_n, days in WEEKS_ALL:
    p = period_data[name]
    ad = p['ad']
    sale_total = p['sales_total']
    is_all = name == '전체'
    w(f'<div class="week-card{" all" if is_all else ""}">')
    holiday_msg = HOLIDAYS.get(name, '')
    holiday_html = f'<span class="holiday">{html.escape(holiday_msg)}</span>' if holiday_msg else ''
    w(f'<div class="week-head"><div class="name">{name}</div><div class="range">{range_str} · {days_n}일</div>{holiday_html}</div>')
    w('<div class="sec-block ad">')
    w('<div class="label"><span class="dot"></span>광고 활동</div>')
    w(f'<div class="big-num">{fmt(ad["clk"])}<small>클릭</small></div>')
    w(f'<div class="stat-row"><span>광고비</span><b>{fmt_won_full(ad["cost"])}</b></div>')
    w(f'<div class="stat-row"><span>광고 기여 구매</span><b>{ad["buy_n"]}건</b></div>')
    w(f'<div class="stat-row"><span>장바구니</span><b>{ad["cart_n"]}건</b></div>')
    w('</div>')
    w('<div class="sec-block sales">')
    w('<div class="label"><span class="dot"></span>실제 매출</div>')
    w(f'<div class="big-num">{fmt_won(sale_total["amt"])}<small>원 · {sale_total["cnt"]}건</small></div>')
    w('<div class="ch-bar">')
    for gname in ['CS', '영업', '스마트스토어', '자사몰', '오픈마켓']:
        members = CHANNEL_GROUPS[gname]
        gv = sum_group(p['sales_by_ch'], members)
        pct = (gv['amt'] / max_ch_amt * 100) if max_ch_amt and gv['amt'] else 0
        w(f'<div class="ch-bar-row"><span class="ch">{html.escape(gname)}</span>'
          f'<div class="bar-wrap"><div class="bar" style="width:{pct:.0f}%"></div></div>'
          f'<span class="val">{fmt_won(gv["amt"])}</span></div>')
    w('</div></div></div>')
w('</div></section>')

# 섹션 2: 통합 비교 표 (클릭 가능)
w('<section><h2><span class="num">2</span>통합 비교 표 <span class="sub">· 숫자 클릭 → 키워드 팝업</span></h2>')
w('<div class="compare-wrap"><table class="compare-table">')
w('<thead>')
w('<tr class="group">')
w('<th rowspan="2" style="vertical-align:middle">기간</th>')
w('<th colspan="3" class="g-ad">광고 활동</th>')
w('<th colspan="6" class="g-sales">실제 매출 (원)</th>')
w('</tr>')
w('<tr class="cols">')
w('<th class="r" style="color:var(--green)">클릭</th>')
w('<th class="r" style="color:var(--green)">광고비</th>')
w('<th class="r" style="color:var(--green)">기여구매</th>')
w('<th class="r" style="color:var(--orange)">CS</th>')
w('<th class="r" style="color:var(--orange)">영업</th>')
w('<th class="r" style="color:var(--orange)">스마트스토어</th>')
w('<th class="r" style="color:var(--orange)">자사몰 (com·kr)</th>')
w('<th class="r" style="color:var(--orange)">오픈마켓</th>')
w('<th class="r" style="color:var(--orange)">전체</th>')
w('</tr></thead><tbody>')
for name, range_str, days_n, days in WEEKS_ALL:
    p = period_data[name]
    ad = p['ad']
    sale = p['sales_by_ch']
    cs = sum_group(sale, ['CS'])['amt']
    yh = sum_group(sale, ['영업'])['amt']
    ss = sum_group(sale, ['스마트스토어','네이버페이','하나몰','더바른사인','로켓출력공장'])['amt']
    js = sum_group(sale, ['고도몰5','신규몰'])['amt']
    op = sum_group(sale, ['쿠팡(신)','G마켓','11번가','옥션'])['amt']
    tot = p['sales_total']['amt']
    is_all = name == '전체'
    cls = ' class="total-row"' if is_all else ''
    w(f'<tr{cls}>')
    w(f'<td><div class="period-name">{name}</div><div style="color:var(--text-dim);font-size:12px">{range_str}</div></td>')
    # 클릭 가능 셀들: data-week, data-type, data-channel
    w(f'<td class="r clk-cell ad-cell" data-week="{name}" data-type="ad" data-ch="click">{fmt(ad["clk"])}</td>')
    w(f'<td class="r ad-cell">{fmt_won_full(ad["cost"])}</td>')
    w(f'<td class="r ad-cell" style="border-right:2px solid var(--border-light)">{ad["buy_n"]}건</td>')
    w(f'<td class="r clk-cell sales-cell" data-week="{name}" data-type="sales" data-ch="CS">{fmt_won_full(cs)}</td>')
    w(f'<td class="r clk-cell sales-cell" data-week="{name}" data-type="sales" data-ch="영업">{fmt_won_full(yh)}</td>')
    w(f'<td class="r clk-cell sales-cell" data-week="{name}" data-type="sales" data-ch="스마트스토어">{fmt_won_full(ss)}</td>')
    w(f'<td class="r clk-cell sales-cell" data-week="{name}" data-type="sales" data-ch="자사몰">{fmt_won_full(js)}</td>')
    w(f'<td class="r clk-cell sales-cell" data-week="{name}" data-type="sales" data-ch="오픈마켓">{fmt_won_full(op)}</td>')
    w(f'<td class="r clk-cell sales-cell" data-week="{name}" data-type="sales" data-ch="전체" style="font-weight:800">{fmt_won_full(tot)}</td>')
    w('</tr>')
w('</tbody></table></div></section>')

# POPUP_DATA JSON 임베드 + JS

# ===== 섹션 3: 광고 상위 30 (탭으로 주차 전환) =====
def render_pname(pid):
    name = pid_name.get(pid, '')
    if not name or name.startswith('nad-'):
        nums = ''.join(ch for ch in pid if ch.isdigit())
        last = nums[-9:] if len(nums) > 9 else nums
        kw_v = f'상품 #{last}' if last else '상품명 미확인'
        full_html = '<div class="full" style="color:#facc15;opacity:0.6">상품명 매핑 안 됨</div>'
    else:
        kw_v = extract_keyword(name)
        if not kw_v: kw_v = name[:30]
        full_html = f'<div class="full">{html.escape(name)}</div>' if name != kw_v else ''
    url = pid_url.get(pid, '')
    store = pid_store.get(pid, '')
    if not store and url:
        if '/rocketprinting/' in url: store = '로켓출력공장'
        elif '/thecorrectsign/' in url: store = '더바른사인'
        elif '/hanasign/' in url: store = '하나몰'
    store_html = f'<span class="store-tag">{html.escape(store)}</span>' if store else ''
    kw_html = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(kw_v)}</a>' if url else html.escape(kw_v)
    return f'<div class="pname"><div class="kw">{store_html}{kw_html}</div>{full_html}</div>'

def top_n_ad(name_w, key, n=30):
    days = next(d for nm,_,_,d in WEEKS_ALL if nm==name_w)
    a = defaultdict(lambda: {'clk':0,'cart_n':0,'cart_v':0,'d_buy_n':0,'d_buy_v':0,'i_buy_n':0,'i_buy_v':0})
    for d in days:
        for pid, v in S['per_day_pid_clk'].get(d, {}).items(): a[pid]['clk'] += v
        for pid, v in S['per_day_pid_cart_n'].get(d, {}).items(): a[pid]['cart_n'] += v
        for pid, v in S['per_day_pid_cart_v'].get(d, {}).items(): a[pid]['cart_v'] += v
        for pid, v in S['per_day_pid_d_buy_n'].get(d, {}).items(): a[pid]['d_buy_n'] += v
        for pid, v in S['per_day_pid_d_buy_v'].get(d, {}).items(): a[pid]['d_buy_v'] += v
        for pid, v in S['per_day_pid_i_buy_n'].get(d, {}).items(): a[pid]['i_buy_n'] += v
        for pid, v in S['per_day_pid_i_buy_v'].get(d, {}).items(): a[pid]['i_buy_v'] += v
    items = [(pid, v) for pid, v in a.items() if v[key] > 0]
    items.sort(key=lambda x: x[1][key], reverse=True)
    return items[:n]

def render_top(items, count_key, value_key, title, ad_total):
    if not items:
        return f'<div class="top-section"><div class="top-title">{title} <span class="sub">데이터 없음</span></div></div>'
    out = [f'<div class="top-section">']
    sub_text = f'합계 {fmt(ad_total[count_key])}건'
    if value_key: sub_text += f' · {fmt_won(ad_total[value_key])}원'
    out.append(f'<div class="top-title">{title} <span class="sub">{sub_text}</span></div>')
    if value_key:
        out.append('<table class="top-table"><thead><tr><th></th><th>상품</th><th class="num">건수</th><th class="num">금액</th></tr></thead><tbody>')
    else:
        out.append('<table class="top-table"><thead><tr><th></th><th>상품</th><th class="num">클릭</th></tr></thead><tbody>')
    for rank, (pid, v) in enumerate(items, 1):
        if value_key:
            out.append(f'<tr><td class="rank">{rank}</td><td>{render_pname(pid)}</td><td class="num">{fmt(v[count_key])}</td><td class="num amt">{fmt_won_full(v[value_key])}</td></tr>')
        else:
            out.append(f'<tr><td class="rank">{rank}</td><td>{render_pname(pid)}</td><td class="num">{fmt(v[count_key])}</td></tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)

w('<section><h2><span class="num">3</span>광고 상위 30 <span class="sub">· 상품별 (탭으로 주차 전환)</span></h2>')
w('<div class="tabs-wrap"><div class="tabs">')
for i, (nm, _, _, _) in enumerate(WEEKS_ALL):
    cls = 'tab-btn active' if i==len(WEEKS_ALL)-1 else 'tab-btn'
    w(f'<button class="{cls}" onclick="showTab({i})">{nm}</button>')
w('</div>')

for i, (nm, rs, dn, ds) in enumerate(WEEKS_ALL):
    cls = 'tab-content active' if i==len(WEEKS_ALL)-1 else 'tab-content'
    ad_total = period_data[nm]['ad']
    w(f'<div id="tab{i}" class="{cls}"><div class="tab-body">')
    w(f'<div class="tab-info">선택 기간 · <b>{nm}</b> · {rs} · 활성 상품 {ad_total["pids"]}개</div>')
    top_clk = top_n_ad(nm, 'clk')
    top_cart = top_n_ad(nm, 'cart_n')
    top_dbuy = top_n_ad(nm, 'd_buy_n')
    top_ibuy = top_n_ad(nm, 'i_buy_n')
    w('<div class="top-grid"><div>')
    w(render_top(top_clk, 'clk', None, '클릭 상위 30', ad_total))
    w(render_top(top_dbuy, 'd_buy_n', 'd_buy_v', '직접구매 상위 30', ad_total))
    w('</div><div>')
    w(render_top(top_cart, 'cart_n', 'cart_v', '장바구니 상위 30', ad_total))
    w(render_top(top_ibuy, 'i_buy_n', 'i_buy_v', '간접구매 상위 30', ad_total))
    w('</div></div></div></div>')
w('</div></section>')

# ===== 섹션 4: 매출 채널별 상위 키워드 (전체 기간) =====
w('<section><h2><span class="num">4</span>매출 상위 키워드 <span class="sub">· 채널별 (전체 기간)</span></h2>')
w('<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:18px">')
# CHANNEL_GROUPS 멤버 평탄화한 채널 순서 — 매출 큰 순
all_chs = []
for gname, members in CHANNEL_GROUPS.items():
    for m in members:
        if period_data['전체']['sales_by_ch'].get(m, {}).get('amt', 0) > 0:
            all_chs.append(m)
# CS, 영업, 그 다음 그룹 멤버들
ordered_chs = ['CS','영업'] + [c for c in all_chs if c not in ('CS','영업')]

for ch in ordered_chs:
    ch_total = period_data['전체']['sales_by_ch'].get(ch, {'cnt':0,'amt':0})
    if ch_total['amt'] <= 0: continue
    # POPUP_DATA에서 채널 키워드 가져오기 — 채널 그룹 합산이 아닌 개별
    # SALES_ROWS에서 직접 키워드 집계 (해당 ch + 전체 기간)
    kw_map = defaultdict(lambda: {'cnt':0,'amt':0})
    for d, week, cat, kw, qty, amt, name in SALES_ROWS:
        if cat != ch: continue
        kw_map[kw]['cnt'] += 1
        kw_map[kw]['amt'] += amt
    top_kws = sorted(kw_map.items(), key=lambda x: -x[1]['amt'])[:10]
    
    w(f'<div style="background:var(--bg-2);border:1px solid var(--border);border-radius:12px;padding:18px">')
    w(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid var(--border)">')
    w(f'<div><span style="font-size:17px;font-weight:700">{html.escape(ch)}</span>')
    w(f'<span style="color:var(--text-dim);font-size:12px;margin-left:6px">{ch_total["cnt"]}건</span></div>')
    w(f'<div style="color:var(--orange);font-weight:700;font-size:15px">{fmt_won_full(ch_total["amt"])}</div>')
    w('</div>')
    if top_kws:
        w('<table class="top-table"><tbody>')
        for rank, (kw_v, v) in enumerate(top_kws, 1):
            w(f'<tr><td class="rank">{rank}</td>')
            w(f'<td><div class="kw" style="font-size:14px;font-weight:600">{html.escape(kw_v)}</div></td>')
            w(f'<td class="num" style="font-size:13px">{v["cnt"]}건</td>')
            w(f'<td class="num amt" style="color:var(--orange)">{fmt_won_full(v["amt"])}</td></tr>')
        w('</tbody></table>')
    w('</div>')
w('</div></section>')



w('<script>')
w('const POPUP_DATA = ' + json.dumps(POPUP_DATA, ensure_ascii=False) + ';')
w("""

const fmtN = n => n.toLocaleString('ko-KR');
const fmtWon = n => {
  if (!n) return '0원';
  if (n >= 100000000) return (n/100000000).toFixed(2) + '억';
  if (n >= 10000000) return (n/10000000).toFixed(1) + '천만';
  if (n >= 10000) return (n/10000).toFixed(0) + '만';
  return n.toLocaleString('ko-KR') + '원';
};
const fmtWonFull = n => n ? n.toLocaleString('ko-KR') + '원' : '0원';

let popupIdx = 0;
function openPopup(week, type, ch, anchorEl){
  popupIdx++;
  const pData = POPUP_DATA[week];
  if(!pData){ console.warn('no week', week); return; }
  
  let title, items, isAd;
  if(type === 'ad'){
    isAd = true;
    title = `<span class="badge">광고</span>클릭 상위 키워드<span class="week">${week} · ${pData.range}</span>`;
    items = pData.ad_click;
  } else {
    isAd = false;
    title = `<span class="badge">매출</span>${ch} 상위 키워드<span class="week">${week} · ${pData.range}</span>`;
    items = pData.sales[ch] || [];
  }
  
  const pop = document.createElement('div');
  pop.className = 'popup';
  
  // 셀 좌표 기준 — 우측에 띄움, 화면 밖이면 좌측, 그래도 안 되면 화면 우측 끝
  const rect = anchorEl.getBoundingClientRect();
  const POP_W = 380;
  const gap = 12;
  let left = rect.right + gap;
  let top = rect.top;
  
  if (left + POP_W > window.innerWidth - 16) {
    // 우측 안 들어가면 좌측 시도
    left = rect.left - POP_W - gap;
    if (left < 16) {
      // 좌측도 안 되면 화면 우측 끝에 붙임
      left = Math.max(16, window.innerWidth - POP_W - 16);
      top = rect.bottom + gap;
    }
  }
  
  // 다중 팝업 오프셋 (같은 자리에 누적되지 않게)
  const offset = (popupIdx - 1) * 22 % 100;
  pop.style.left = (left + offset) + 'px';
  pop.style.top = (top + offset) + 'px';
  
  let html = `<div class="popup-head ${isAd?'ad':'sales'}">
    <div class="title">${title}</div>
    <button class="popup-close" aria-label="닫기">×</button>
  </div><div class="popup-body">`;
  if(items.length === 0){
    html += '<div style="padding:20px;color:#94a3b8;font-size:13px;text-align:center">데이터 없음</div>';
  } else if(isAd){
    html += '<table><thead><tr><th></th><th>상품 키워드</th><th class="num">클릭</th></tr></thead><tbody>';
    items.forEach((it, i) => {
      html += `<tr><td class="rank">${i+1}</td><td class="kw">${escapeHtml(it[0])}</td><td class="num ad-num">${fmtN(it[1])}</td></tr>`;
    });
    html += '</tbody></table>';
  } else {
    html += '<table><thead><tr><th></th><th>상품 키워드</th><th class="num">건수</th><th class="num">매출</th></tr></thead><tbody>';
    items.forEach((it, i) => {
      html += `<tr><td class="rank">${i+1}</td><td class="kw">${escapeHtml(it[0])}</td><td class="num">${it[1]}</td><td class="num amt">${fmtWonFull(it[2])}</td></tr>`;
    });
    html += '</tbody></table>';
  }
  html += '</div>';
  pop.innerHTML = html;
  document.body.appendChild(pop);
  
  // 닫기
  pop.querySelector('.popup-close').addEventListener('click', () => pop.remove());
  
  // 드래그
  const head = pop.querySelector('.popup-head');
  let dragging = false, dx = 0, dy = 0;
  head.addEventListener('mousedown', e => {
    if(e.target.classList.contains('popup-close')) return;
    dragging = true;
    const rect = pop.getBoundingClientRect();
    dx = e.clientX - rect.left;
    dy = e.clientY - rect.top;
    pop.style.transition = 'none';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('mousemove', e => {
    if(!dragging) return;
    pop.style.left = (e.clientX - dx) + 'px';
    pop.style.top = (e.clientY - dy) + 'px';
  });
  document.addEventListener('mouseup', () => {
    if(dragging){ dragging = false; document.body.style.userSelect = ''; }
  });
  
  // 터치 드래그
  head.addEventListener('touchstart', e => {
    if(e.target.classList.contains('popup-close')) return;
    const t = e.touches[0];
    const rect = pop.getBoundingClientRect();
    dx = t.clientX - rect.left;
    dy = t.clientY - rect.top;
    dragging = true;
  }, {passive:true});
  document.addEventListener('touchmove', e => {
    if(!dragging) return;
    const t = e.touches[0];
    pop.style.left = (t.clientX - dx) + 'px';
    pop.style.top = (t.clientY - dy) + 'px';
  }, {passive:true});
  document.addEventListener('touchend', () => dragging = false);
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function showTab(i){
  document.querySelectorAll('.tab-btn').forEach((b,idx)=>b.classList.toggle('active', idx===i));
  document.querySelectorAll('.tab-content').forEach((c,idx)=>c.classList.toggle('active', idx===i));
}

document.querySelectorAll('.clk-cell').forEach(td => {
  td.addEventListener('click', () => {
    const week = td.dataset.week;
    const type = td.dataset.type;
    const ch = td.dataset.ch;
    openPopup(week, type, ch, td);
  });
});
""")
w('</script>')

w("""<footer>
  하나사인몰 웹팀 · 광고 자동화 + 매출 데이터 통합 · 클릭 가능한 대화형 보고서
</footer>
</div>
</body></html>""")

open('/tmp/dark_report.html', 'w', encoding='utf-8').write(''.join(buf))
import os
local = '/sessions/serene-dazzling-hypatia/mnt/outputs/주월보고서/주월간_종합비교_2026-05-27.html'
os.makedirs(os.path.dirname(local), exist_ok=True)
open(local, 'w', encoding='utf-8').write(''.join(buf))
print(f'생성 완료: {os.path.getsize(local):,} bytes')
