#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
하나사인몰 광고 주간 보고서 v2 — 환경변수 + 상품 단위 합산 + 장바구니 + 실매출
사용법:
  python3 build_weekly_v2.py                # 최근 7일 (어제 KST 종료)
  python3 build_weekly_v2.py 2026-05-18     # 그 날까지 최근 7일
  python3 build_weekly_v2.py 2026-05-18 14  # 14일
  python3 build_weekly_v2.py 2026-05-18 30  # 30일
"""
import csv, io, json, urllib.request, urllib.parse, hmac, hashlib, base64, time, sys, datetime, ssl, os
from collections import defaultdict

A_KEY = os.environ["A_KEY"]; A_SEC = os.environ["A_SEC"]; A_CID = "1728536"
B_KEY = os.environ["B_KEY"]; B_SEC = os.environ["B_SEC"]; B_CID = "1558945"
N_BASE = "https://api.searchad.naver.com"
SHEET = "1Yuw_8we4nEzL1nslHI66LHBBE_uWc-ErALzhn2vvLGI"
SALES_SHEET = "169BTstGNSOPxx0aKglV2sTb_zhZWEfW1KTcht-K3afA"
SALES_GID = 1952467949

if len(sys.argv) > 1:
    END = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
else:
    kst = datetime.timezone(datetime.timedelta(hours=9))
    END = datetime.datetime.now(kst).date() - datetime.timedelta(days=1)
DAYS_RANGE = int(sys.argv[2]) if len(sys.argv) > 2 else 7
START = END - datetime.timedelta(days=DAYS_RANGE-1)
DATES = [(START + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DAYS_RANGE)]
print(f"[start] {START} ~ {END} ({DAYS_RANGE}일)", file=sys.stderr)

ctx = ssl._create_unverified_context()

def to_int(s, d=0):
    try: return int(float((s or "0").replace(",","")))
    except: return d

def gviz_csv(sheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    return list(csv.reader(io.StringIO(urllib.request.urlopen(url, context=ctx, timeout=30).read().decode("utf-8"))))

def n_sign(secret, m, p):
    ts = str(int(time.time()*1000))
    return ts, base64.b64encode(hmac.new(secret.encode(), f"{ts}.{m}.{p}".encode(), hashlib.sha256).digest()).decode()

def n_req(key, secret, cid, m, p, body=None):
    ts, sig = n_sign(secret, m, p.split("?")[0])
    H = {"X-Timestamp":ts,"X-API-KEY":key,"X-Customer":cid,"X-Signature":sig,"Content-Type":"application/json"}
    data = json.dumps(body).encode() if body else None
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(N_BASE+p, data=data, method=m, headers=H), context=ctx, timeout=20).read())
    except: return None

def n_stat(key, secret, cid, reportTp, statDt, max_wait=90):
    rsp = n_req(key, secret, cid, "POST", "/stat-reports", {"reportTp":reportTp,"statDt":statDt})
    if not rsp: return None
    rid = rsp.get("reportJobId") or rsp.get("id")
    if not rid: return None
    t0 = time.time()
    while time.time() - t0 < max_wait:
        time.sleep(2)
        info = n_req(key, secret, cid, "GET", f"/stat-reports/{rid}")
        if not info: continue
        st = info.get("status")
        if st in ("BUILT","REGISTERED","DONE"):
            durl = info.get("downloadUrl")
            if durl:
                ts2, sig2 = n_sign(secret, "GET", urllib.parse.urlparse(durl).path)
                try: return urllib.request.urlopen(urllib.request.Request(durl, headers={"X-Timestamp":ts2,"X-API-KEY":key,"X-Customer":cid,"X-Signature":sig2}), context=ctx, timeout=30).read().decode("utf-8","ignore")
                except: return None
        if st in ("FAILED","EXPIRED","NONE"): return None
    return None

# 상품매핑
mp = {}
try:
    for r in gviz_csv(SHEET, 1248602534)[1:]:
        if not r or not r[0]: continue
        pid = r[0].strip(); name = r[1].strip() if len(r)>1 else ""
        pno = r[3].strip() if len(r)>3 else ""
        url = pno if pno.startswith("http") else (f"https://smartstore.naver.com/hanasign/products/{pno}" if pno else "")
        mp[pid] = {"name":name, "url":url}
    print(f"  상품매핑 {len(mp)}개", file=sys.stderr)
except Exception as e: print(f"  매핑 err: {e}", file=sys.stderr)

# 캠페인/광고그룹 이름
a_camps = n_req(A_KEY,A_SEC,A_CID,"GET","/ncc/campaigns") or []
a_cidx = {c["nccCampaignId"]:c["name"] for c in a_camps if isinstance(c,dict)}
a_adgs = n_req(A_KEY,A_SEC,A_CID,"GET","/ncc/adgroups") or []
a_aidx = {a["nccAdgroupId"]:a["name"] for a in a_adgs if isinstance(a,dict)}

# A 데이터 일자별 수집
print(f"\n[1] A 데이터 수집 ({DAYS_RANGE}일)", file=sys.stderr)
a_all = []; a_buy = {}
for dt in DATES:
    tsv = n_stat(A_KEY,A_SEC,A_CID,"AD",dt)
    if tsv:
        for line in tsv.splitlines():
            cols = line.split("\t")
            if len(cols)<12: continue
            try:
                imp=int(float(cols[-5].replace(",",""))); clk=int(float(cols[-4].replace(",",""))); cost=int(float(cols[-3].replace(",","")))
            except: imp=clk=cost=0
            cid=cols[2]; agid=cols[3]; pid=cols[5] if len(cols)>5 else ""
            a_all.append({"date":dt,"campaign":a_cidx.get(cid,cid),"adgroup":a_aidx.get(agid,agid),"pid":pid,
                "imp":imp,"clk":clk,"cost":cost,"name":mp.get(pid,{}).get("name",pid),"url":mp.get(pid,{}).get("url","")})
    tsv = n_stat(A_KEY,A_SEC,A_CID,"AD_CONVERSION",dt)
    if tsv:
        for line in tsv.splitlines():
            cols = line.split("\t")
            if len(cols)<13: continue
            try:
                pid=cols[5]; ctype=cols[10]
                cnt=int(float(cols[11].replace(",",""))); val=int(float(cols[12].replace(",","")))
            except: continue
            if pid not in a_buy: a_buy[pid] = {"buy_n":0,"buy_v":0,"cart_n":0,"cart_v":0}
            if ctype=="purchase": a_buy[pid]["buy_n"]+=cnt; a_buy[pid]["buy_v"]+=val
            elif ctype=="add_to_cart": a_buy[pid]["cart_n"]+=cnt; a_buy[pid]["cart_v"]+=val
    print(f"  {dt}: cum rows {len(a_all)}", file=sys.stderr)

# dedupe
_d = {}
for r in a_all:
    k = (r["pid"], r["campaign"], r["adgroup"])
    if k not in _d:
        _d[k] = {**r}; _d[k]["dates"] = {r["date"]}
    else:
        _d[k]["imp"]+=r["imp"]; _d[k]["clk"]+=r["clk"]; _d[k]["cost"]+=r["cost"]; _d[k]["dates"].add(r["date"])
a_rows = list(_d.values())
print(f"  A dedupe: {len(a_all)} → {len(a_rows)}", file=sys.stderr)

# 상품 단위 합산
agg = {}
for r in a_rows:
    k = (r.get("name") or r["pid"]).strip() or r["pid"]
    if k not in agg:
        agg[k] = {"name":k,"url":r.get("url",""),"mall":"","imp":0,"clk":0,"cost":0,"_pids":set(),"_camps":set(),"_grps":set()}
    agg[k]["imp"]+=r["imp"]; agg[k]["clk"]+=r["clk"]; agg[k]["cost"]+=r["cost"]
    agg[k]["_pids"].add(r["pid"]); agg[k]["_camps"].add(r["campaign"]); agg[k]["_grps"].add(r["adgroup"])
    _u = r.get("url","")
    if not agg[k]["mall"]:
        if "/hanasign/" in _u: agg[k]["mall"] = "하나몰"
        elif "/thecorrectsign/" in _u: agg[k]["mall"] = "더바른사인"
        elif "/rocketprinting/" in _u: agg[k]["mall"] = "로켓출력공장"
a_by_name = []
for v in agg.values():
    v["_pids"] = sorted(v["_pids"]); v["_camps"] = sorted(v["_camps"]); v["_grps"] = sorted(v["_grps"])
    bv = sum(a_buy.get(p,{}).get("buy_v",0) for p in v["_pids"])
    bn = sum(a_buy.get(p,{}).get("buy_n",0) for p in v["_pids"])
    cv = sum(a_buy.get(p,{}).get("cart_v",0) for p in v["_pids"])
    cn = sum(a_buy.get(p,{}).get("cart_n",0) for p in v["_pids"])
    v["buy_v"]=bv; v["buy_n"]=bn; v["cart_v"]=cv; v["cart_n"]=cn
    v["ctr"] = round(v["clk"]/v["imp"]*100, 2) if v["imp"] else 0
    v["roas"] = round(bv/v["cost"]*100, 1) if v["cost"] else 0
    a_by_name.append(v)
a_by_name.sort(key=lambda x:-x["cost"])

# === B 데이터 수집 ===
print(f"\n[1-B] B 데이터 수집 ({DAYS_RANGE}일)", file=sys.stderr)
b_camps_api = n_req(B_KEY,B_SEC,B_CID,"GET","/ncc/campaigns") or []
b_cidx = {c["nccCampaignId"]:c["name"] for c in b_camps_api if isinstance(c,dict)}
b_adgs_api = n_req(B_KEY,B_SEC,B_CID,"GET","/ncc/adgroups") or []
b_aidx = {a["nccAdgroupId"]:{"name":a["name"],"cid":a.get("nccCampaignId","")} for a in b_adgs_api if isinstance(a,dict)}
b_total = {"imp":0,"clk":0,"cost":0}
b_adg = defaultdict(lambda:{"imp":0,"clk":0,"cost":0,"name":"","campaign":""})
b_conv = {"n":0,"v":0}
for dt in DATES:
    tsv = n_stat(B_KEY,B_SEC,B_CID,"AD",dt)
    if tsv:
        for line in tsv.splitlines():
            cols = line.split("\t")
            if len(cols)<12: continue
            try:
                imp=int(float(cols[-5].replace(",",""))); clk=int(float(cols[-4].replace(",",""))); cost=int(float(cols[-3].replace(",","")))
            except: imp=clk=cost=0
            cid=cols[2]; agid=cols[3]
            b_total["imp"]+=imp; b_total["clk"]+=clk; b_total["cost"]+=cost
            if agid in b_aidx:
                a = b_adg[agid]
                a["name"] = b_aidx[agid]["name"]
                a["campaign"] = b_cidx.get(b_aidx[agid]["cid"],"")
                a["imp"]+=imp; a["clk"]+=clk; a["cost"]+=cost
    tsv = n_stat(B_KEY,B_SEC,B_CID,"AD_CONVERSION",dt)
    if tsv:
        for line in tsv.splitlines():
            cols = line.split("\t")
            if len(cols)<13: continue
            try:
                ctype=cols[10]; cnt=int(float(cols[11].replace(",",""))); val=int(float(cols[12].replace(",","")))
            except: continue
            if ctype=="purchase": b_conv["n"]+=cnt; b_conv["v"]+=val
    print(f"  {dt}: B cum cost " + f"{b_total['cost']:,}", file=sys.stderr)
b_adgs = sorted(b_adg.values(), key=lambda x:-x["cost"])
print(f"  B 광고그룹 {len(b_adgs)}개", file=sys.stderr)

# 실매출 시트
print(f"\n[2] 실매출 시트", file=sys.stderr)
sales_rows = []
try:
    rows = gviz_csv(SALES_SHEET, SALES_GID)
    h = rows[0] if rows else []
    iy=im=id_=imgr=iamt=-1
    for i,col in enumerate(h):
        col=(col or "").strip()
        if col=="년": iy=i
        elif col=="월": im=i
        elif col=="일": id_=i
        elif col=="진행자": imgr=i
        elif col in ("총 금액","총금액"): iamt=i
    print(f"  컬럼: 년={iy} 월={im} 일={id_} 진행자={imgr} 총금액={iamt}", file=sys.stderr)
    if all(i>=0 for i in [iy,im,id_,imgr,iamt]):
        for r in rows[1:]:
            try:
                y=int(float(r[iy])); mo=int(float(r[im])); d=int(float(r[id_]))
                date=f"{y:04d}-{mo:02d}-{d:02d}"
                if date<DATES[0] or date>DATES[-1]: continue
                sales_rows.append({"date":date,"mgr":(r[imgr] or "").strip(),"amt":to_int(r[iamt])})
            except: continue
    print(f"  기간 내 {len(sales_rows)}건", file=sys.stderr)
except Exception as e: print(f"  err: {e}", file=sys.stderr)

def cls_ch(mgr):
    if "(영호)" in mgr: return "영업(영호)"
    if mgr=="스마트스토어": return "스마트스토어"
    if mgr=="고도몰5": return "자사몰(고도몰)"
    if mgr=="신규몰": return "자사몰(신규몰)"
    if mgr=="쿠팡(신)": return "쿠팡"
    if mgr in ("G마켓","옥션"): return "G마켓/옥션"
    if mgr.startswith("사인몰") or mgr.startswith("하나몰"): return "CS"
    return f"기타({mgr})"
sales_by_ch = defaultdict(lambda:{"cnt":0,"amt":0})
for s in sales_rows:
    ch = cls_ch(s["mgr"])
    sales_by_ch[ch]["cnt"]+=1; sales_by_ch[ch]["amt"]+=s["amt"]

# === 통계 출력 ===
print(f"\n{'='*60}")
print(f"=== {START} ~ {END} ({DAYS_RANGE}일) ===")
print(f"{'='*60}\n")
a_total = {"imp":sum(r["imp"] for r in a_rows),"clk":sum(r["clk"] for r in a_rows),"cost":sum(r["cost"] for r in a_rows)}
total_buy = sum(b["buy_v"] for b in a_buy.values()); total_cart = sum(b["cart_v"] for b in a_buy.values())
print(f"[A 스마트스토어]  광고비 {a_total['cost']:>10,} / 노출 {a_total['imp']:,} / 클릭 {a_total['clk']:,} / CTR {a_total['clk']/a_total['imp']*100:.2f}%")
print(f"  매출 {total_buy:,}원 ({sum(b['buy_n'] for b in a_buy.values())}건) / 장바구니 {total_cart:,}원 / 상품 {len(a_by_name)}개")
print()
print(f"[실매출 시트 — 채널별]")
for ch,v in sorted(sales_by_ch.items(), key=lambda x:-x[1]["amt"]):
    print(f"  {ch:<20} {v['cnt']:>3}건  {v['amt']:>12,}원")
print(f"  합계: {sum(v['cnt'] for v in sales_by_ch.values())}건  {sum(v['amt'] for v in sales_by_ch.values()):,}원")
print()
print(f"[A 상품 TOP 15 — 광고비순]")
print(f"{'순위':>3} {'광고비':>8} {'클릭':>5} {'CTR':>7} {'매출':>9} {'장바구니':>9} {'상품명'}")
for i,p in enumerate(a_by_name[:15],1):
    print(f"  {i:>2} {p['cost']:>8,} {p['clk']:>5} {p['ctr']:>6.2f}% {p['buy_v']:>9,} {p['cart_v']:>9,} {p['name'][:50]}")
print()
print(f"[A 상품 TOP 15 — CTR순 (클릭 10+ 필터)]")
ct = sorted([p for p in a_by_name if p['clk']>=10], key=lambda x:-x['ctr'])[:15]
print(f"{'순위':>3} {'CTR':>7} {'클릭':>5} {'노출':>6} {'광고비':>8} {'상품명'}")
for i,p in enumerate(ct,1):
    print(f"  {i:>2} {p['ctr']:>6.2f}% {p['clk']:>5} {p['imp']:>6,} {p['cost']:>8,} {p['name'][:50]}")
print()
print(f"[A 장바구니 TOP 10]")
ca = sorted([p for p in a_by_name if p['cart_v']>0], key=lambda x:-x['cart_v'])[:10]
print(f"{'순위':>3} {'장바구니':>10} {'건수':>4} {'광고비':>8} {'상품명'}")
for i,p in enumerate(ca,1):
    print(f"  {i:>2} {p['cart_v']:>10,} {p['cart_n']:>4} {p['cost']:>8,} {p['name'][:50]}")


# ============ HTML 빌드 ============
print(f"\n[HTML 빌드]", file=sys.stderr)

# 정렬 가능한 상품 표 데이터 (TOP 50 — 광고비순)
table_data = []
for p in a_by_name[:50]:
    table_data.append({
        "name": p["name"], "url": p["url"], "mall": p.get("mall",""),
        "imp": p["imp"], "clk": p["clk"], "ctr": p["ctr"], "cost": p["cost"],
        "buy_n": p["buy_n"], "buy_v": p["buy_v"],
        "cart_n": p["cart_n"], "cart_v": p["cart_v"],
        "roas": p["roas"],
        "camps": len(p["_camps"]), "grps": len(p["_grps"]),
    })

# 일별 추이
day_trend = []
for dt in DATES:
    rs = [r for r in a_all if r["date"] == dt]
    bs = [v for v in a_buy.values()]  # 일별 분리 안되어 있어 합계만
    day_trend.append({
        "date": dt,
        "cost": sum(r["cost"] for r in rs),
        "clk": sum(r["clk"] for r in rs),
        "imp": sum(r["imp"] for r in rs),
    })

# 매출은 a_buy 전체기간 합산이라 일별 분리는 별도 — 일단 합산만
total_buy_v = sum(b["buy_v"] for b in a_buy.values())
total_buy_n = sum(b["buy_n"] for b in a_buy.values())
total_cart_v = sum(b["cart_v"] for b in a_buy.values())
total_cart_n = sum(b["cart_n"] for b in a_buy.values())

# B 광고그룹 TOP 50
b_table = []
for a in b_adgs[:50]:
    ctr = round(a["clk"]/a["imp"]*100, 2) if a["imp"] else 0
    cpc = round(a["cost"]/a["clk"]) if a["clk"] else 0
    b_table.append({
        "name": a["name"], "campaign": a["campaign"],
        "imp": a["imp"], "clk": a["clk"], "cost": a["cost"], "ctr": ctr, "cpc": cpc,
    })

# A products에 cpc 추가
for p in table_data:
    p["cpc"] = round(p["cost"]/p["clk"]) if p["clk"] else 0

# === 줄여도 될 광고 후보 — 3그룹 분류 ===
# 카테고리: 전화 주문 가능 (대량 주문 비중 큼)
PHONE_CATS = ["주차스티커","주차증","바닥","현수막","배너","피난안내도","시트지","포맥스","페트","폼보드","실사출력","PVC켈지","PET지","대량"]
def _is_phone(name):
    return any(c in (name or "") for c in PHONE_CATS)
def _cat_label(name):
    n = name or ""
    if "주차스티커" in n or "주차증" in n: return "📞 주차스티커 (전화↑)"
    if "피난안내도" in n: return "📞 피난안내도 (전화↑)"
    if "바닥" in n: return "📞 바닥 (전화↑)"
    if "현수막" in n or "배너" in n: return "📞 현수막 (전화↑)"
    if "포맥스" in n or "페트" in n or "시트지" in n or "PVC" in n or "PET" in n or "실사출력" in n or "폼보드" in n: return "📞 실사출력 (전화↑)"
    if "게시판" in n: return "🛒 게시판"
    if "안내판" in n or "표지판" in n or "알림판" in n: return "🛒 안내판"
    if "입간판" in n: return "🛒 입간판"
    if "스티커" in n: return "🛒 스티커"
    return "🛒 기타"
def _to_cut(p):
    return {"name":p["name"],"url":p.get("url",""),"imp":p["imp"],"clk":p["clk"],"ctr":p["ctr"],
            "cost":p["cost"],"buy_v":p["buy_v"],"cart_v":p["cart_v"],"roas":p["roas"],
            "cat":_cat_label(p["name"])}

# Group 1: 확실히 줄일 — CTR <0.1% & 노출 >=5000 (관심도 자체 없음, 카테고리 무관)
g1_clear = sorted([p for p in a_by_name if p["ctr"]<0.1 and p["imp"]>=5000], key=lambda x:-x["cost"])[:15]
# Group 2: 재검토 (전화 주문 가능) — 광고비 >=30k & 매출 0 & PHONE_CATS
g2_review = sorted([p for p in a_by_name if p["cost"]>=30000 and p["buy_v"]==0 and _is_phone(p["name"])], key=lambda x:-x["cost"])[:15]
# Group 3: OFF 가능 — 광고비 >=30k & 매출 0 & 전화 카테고리 아님 (온라인 결제 카테고리)
g3_off = sorted([p for p in a_by_name if p["cost"]>=30000 and p["buy_v"]==0 and not _is_phone(p["name"])], key=lambda x:-x["cost"])[:15]

cut_clear = [_to_cut(p) for p in g1_clear]
cut_review = [_to_cut(p) for p in g2_review]
cut_off = [_to_cut(p) for p in g3_off]
cut_clear_total = sum(p["cost"] for p in g1_clear)
cut_review_total = sum(p["cost"] for p in g2_review)
cut_off_total = sum(p["cost"] for p in g3_off)

D = {
    "meta": {
        "start": START.strftime("%Y-%m-%d"),
        "end": END.strftime("%Y-%m-%d"),
        "days": DAYS_RANGE,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    },
    "a_total": {
        "cost": a_total["cost"], "imp": a_total["imp"], "clk": a_total["clk"],
        "ctr": round(a_total["clk"]/a_total["imp"]*100, 2) if a_total["imp"] else 0,
        "cpc": round(a_total["cost"]/a_total["clk"]) if a_total["clk"] else 0,
        "buy_v": total_buy_v, "buy_n": total_buy_n,
        "cart_v": total_cart_v, "cart_n": total_cart_n,
        "roas": round(total_buy_v/a_total["cost"]*100, 1) if a_total["cost"] else 0,
        "products": len(a_by_name),
    },
    "b_total": {
        "cost": b_total["cost"], "imp": b_total["imp"], "clk": b_total["clk"],
        "ctr": round(b_total["clk"]/b_total["imp"]*100, 2) if b_total["imp"] else 0,
        "cpc": round(b_total["cost"]/b_total["clk"]) if b_total["clk"] else 0,
        "buy_v": b_conv["v"], "buy_n": b_conv["n"],
        "roas": round(b_conv["v"]/b_total["cost"]*100, 1) if b_total["cost"] else 0,
        "adgroups": len(b_adgs),
    },
    "combined": {
        "cost": a_total["cost"] + b_total["cost"],
        "buy_v": total_buy_v + b_conv["v"],
    },
    "products": table_data,
    "b_adgroups": b_table,
    "day_trend": day_trend,
    "cut": {"clear":cut_clear,"review":cut_review,"off":cut_off,"clear_total":cut_clear_total,"review_total":cut_review_total,"off_total":cut_off_total},
}

# 간단 HTML (다크 테마, 정렬 가능한 표)
html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>광고 주간 보고서 {D['meta']['start']} ~ {D['meta']['end']}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #0a0e1a; color: #e2e8f0; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; padding: 20px; }}
.wrap {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin: 0 0 6px; color: #fff; }}
.sub {{ color: #94a3b8; font-size: 13px; margin-bottom: 24px; }}
.matrix {{ display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
.matrix > div {{ background: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 16px; }}
.matrix .head {{ display:flex; align-items:center; gap:8px; margin-bottom:12px; font-size:14px; font-weight:700; color:#fff; }}
.matrix .badge {{ font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }}
.matrix .kpi-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:8px; }}
.matrix .item {{ background:#0f172a; border-radius:6px; padding:8px 10px; }}
.matrix .item .l {{ color:#94a3b8; font-size:10px; }}
.matrix .item .v {{ color:#fff; font-size:15px; font-weight:600; margin-top:2px; }}
.section {{ background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
h2 {{ font-size: 16px; margin: 0 0 6px; color: #fff; display: flex; align-items: center; gap: 8px; }}
.num {{ background: #3b82f6; color: #fff; width: 24px; height: 24px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }}
.num.naver {{ background: #03c75a; }}
.num.power {{ background: #6366f1; }}
.desc {{ color: #94a3b8; font-size: 12px; margin-bottom: 14px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{ background: #0f172a; color: #94a3b8; padding: 10px 8px; text-align: left; border-bottom: 1px solid #1e293b; cursor: pointer; user-select: none; font-weight: 600; }}
th:hover {{ background: #1e293b; }}
th .sort {{ opacity: 0.3; margin-left: 4px; font-size: 10px; }}
th.asc .sort, th.desc .sort {{ opacity: 1; color: #3b82f6; }}
td {{ padding: 8px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }}
td.r {{ text-align: right; }}
td.bold {{ font-weight: 600; color: #fff; }}
tr:hover td {{ background: #0f172a; }}
.bar {{ display: inline-block; height: 5px; background: #3b82f6; border-radius: 2px; vertical-align: middle; margin-right: 6px; }}
a {{ color: inherit; text-decoration: none; border-bottom: 1px dotted #475569; }}
a:hover {{ border-bottom-color: #3b82f6; color: #fff; }}
.muted {{ color: #64748b; }}
.green {{ color: #4ade80; }}
.yellow {{ color: #fbbf24; }}
.trend {{ display: grid; grid-template-columns: repeat({D['meta']['days']}, 1fr); gap: 6px; margin-top: 12px; }}
.trend-cell {{ background: #0f172a; border-radius: 4px; padding: 8px; text-align: center; font-size: 11px; }}
.trend-cell .d {{ color: #94a3b8; }}
.trend-cell .v {{ color: #fff; font-weight: 600; margin-top: 2px; }}
</style>
</head>
<body>
<div class="wrap">
<h1>📊 하나사인몰 광고 주간 보고서</h1>
<div class="sub">{D['meta']['start']} ~ {D['meta']['end']} · {D['meta']['days']}일 · 생성 {D['meta']['generated_at']}</div>

<div class="matrix">
  <div>
    <div class="head"><span style="background:#03c75a;color:#fff;padding:3px 8px;border-radius:4px;font-size:11px">N</span>검색광고 (스마트스토어)<span class="badge" style="background:#1e293b;color:#94a3b8">A 계정</span></div>
    <div class="kpi-grid">
      <div class="item"><div class="l">광고비</div><div class="v">{D['a_total']['cost']:,}원</div></div>
      <div class="item"><div class="l">매출</div><div class="v" style="color:#4ade80">{D['a_total']['buy_v']:,}원</div></div>
      <div class="item"><div class="l">클릭 (CTR)</div><div class="v">{D['a_total']['clk']:,} ({D['a_total']['ctr']}%)</div></div>
      <div class="item"><div class="l">ROAS</div><div class="v">{D['a_total']['roas']}%</div></div>
      <div class="item"><div class="l">장바구니</div><div class="v" style="color:#fbbf24">{D['a_total']['cart_v']:,}원</div></div>
      <div class="item"><div class="l">상품 수</div><div class="v">{D['a_total']['products']}</div></div>
    </div>
  </div>
  <div>
    <div class="head"><span style="background:#6366f1;color:#fff;padding:3px 8px;border-radius:4px;font-size:11px">N</span>파워링크 (자사몰)<span class="badge" style="background:#1e293b;color:#94a3b8">B 계정</span></div>
    <div class="kpi-grid">
      <div class="item"><div class="l">광고비</div><div class="v">{D['b_total']['cost']:,}원</div></div>
      <div class="item"><div class="l">매출</div><div class="v" style="color:#4ade80">{D['b_total']['buy_v']:,}원</div></div>
      <div class="item"><div class="l">클릭 (CTR)</div><div class="v">{D['b_total']['clk']:,} ({D['b_total']['ctr']}%)</div></div>
      <div class="item"><div class="l">ROAS</div><div class="v">{D['b_total']['roas']}%</div></div>
      <div class="item"><div class="l">CPC</div><div class="v">{D['b_total']['cpc']:,}원</div></div>
      <div class="item"><div class="l">광고그룹</div><div class="v">{D['b_total']['adgroups']}</div></div>
    </div>
  </div>
  <div>
    <div class="head">📊 합산<span class="badge" style="background:#1e293b;color:#94a3b8">A+B</span></div>
    <div class="kpi-grid">
      <div class="item"><div class="l">총 광고비</div><div class="v">{D['combined']['cost']:,}원</div></div>
      <div class="item"><div class="l">총 매출</div><div class="v" style="color:#4ade80">{D['combined']['buy_v']:,}원</div></div>
      <div class="item" style="grid-column:span 2"><div class="l">통합 ROAS</div><div class="v" style="font-size:18px">{round(D['combined']['buy_v']/D['combined']['cost']*100,1) if D['combined']['cost'] else 0}%</div></div>
    </div>
  </div>
</div>

<div class="section">
  <h2><span class="num">1</span>일별 광고비 추이 (A+B 합산)</h2>
  <div class="desc">기간 내 일별 검색광고(A) 광고비. 평일/주말 패턴 확인.</div>
  <div class="trend">
"""
maxcost = max(d["cost"] for d in day_trend) or 1
for d in day_trend:
    wkd = ["월","화","수","목","금","토","일"][datetime.datetime.strptime(d["date"],"%Y-%m-%d").weekday()]
    h_pct = int(d["cost"]/maxcost*40)
    html += f'''<div class="trend-cell"><div class="d">{d['date'][5:]} ({wkd})</div><div style="height:{h_pct}px;background:#3b82f6;margin:6px auto 4px;width:60%;border-radius:2px"></div><div class="v">{d['cost']:,}원</div><div class="muted" style="font-size:10px">{d['clk']}클릭</div></div>'''
html += """
  </div>
</div>

<div class="section">
  <h2><span class="num naver">2</span>검색광고 (스마트스토어) — 상품 단위 TOP 50</h2>
  <div class="desc">소재가 아닌 상품 단위로 합산. 같은 상품을 여러 캠페인에 등록한 경우 묶임. 좌측 아이콘은 채널(하나몰/더바른사인/로켓). <b>컬럼 헤더 클릭하면 정렬 토글</b>.</div>
  <table id="atbl">
    <thead><tr>
      <th data-key="rank">#</th>
      <th data-key="name">상품명</th>
      <th data-key="cost" class="r">광고비<span class="sort">▼</span></th>
      <th data-key="imp" class="r">노출<span class="sort">⇅</span></th>
      <th data-key="clk" class="r">클릭<span class="sort">⇅</span></th>
      <th data-key="ctr" class="r">CTR<span class="sort">⇅</span></th>
      <th data-key="buy_v" class="r">매출<span class="sort">⇅</span></th>
      <th data-key="buy_n" class="r">건수<span class="sort">⇅</span></th>
      <th data-key="cart_v" class="r">장바구니<span class="sort">⇅</span></th>
      <th data-key="roas" class="r">ROAS<span class="sort">⇅</span></th>
      <th data-key="camps" class="r">캠수<span class="sort">⇅</span></th>
    </tr></thead>
    <tbody id="atb"></tbody>
  </table>
</div>

<div class="section">
  <h2><span class="num" style="background:#f59e0b">4</span>줄여도 될 광고 후보</h2>
  <div class="desc">3그룹으로 분류 — <b style="color:#ef4444">명백히 OFF 가능</b>(온라인 결제 카테고리에서 매출 0) / <b style="color:#fbbf24">재검토 필요</b>(주차·바닥·현수막·실사출력 등 전화 주문 비중 큰 카테고리) / <b style="color:#a855f7">확실히 줄일</b>(CTR <0.1% — 관심도 자체가 없음). 카테고리 아이콘: 📞 = 전화 주문 가능, 🛒 = 온라인 결제 중심.</div>
  <div id="cut_off_area"></div>
  <div id="cut_low_ctr_area" style="margin-top:14px"></div>
  <div id="cut_low_roas_area" style="margin-top:14px"></div>
</div>

<div class="section">
  <h2><span class="num power">5</span>파워링크 (자사몰) — 광고그룹 TOP 50</h2>
  <div class="desc">파워링크는 광고그룹 단위로 운영. 자사몰(고도몰/신규몰) 트래픽 유도용. <b>컬럼 헤더 클릭하면 정렬 토글</b>.</div>
  <table id="btbl">
    <thead><tr>
      <th data-key="rank">#</th>
      <th data-key="name">광고그룹</th>
      <th data-key="campaign">캠페인</th>
      <th data-key="cost" class="r">광고비<span class="sort">▼</span></th>
      <th data-key="imp" class="r">노출<span class="sort">⇅</span></th>
      <th data-key="clk" class="r">클릭<span class="sort">⇅</span></th>
      <th data-key="ctr" class="r">CTR<span class="sort">⇅</span></th>
    </tr></thead>
    <tbody id="btb"></tbody>
  </table>
</div>

</div>

<script>
const D = """ + json.dumps(D, ensure_ascii=False) + """;
function fmt(n){ return Number(n||0).toLocaleString('ko-KR'); }
function mallIcon(mall){
  const map = {
    "하나몰": '<span style="display:inline-block;background:#10b981;color:#fff;width:18px;height:18px;border-radius:4px;font-size:10px;text-align:center;line-height:18px;font-weight:700;margin-right:6px;vertical-align:middle" title="하나몰">하</span>',
    "더바른사인": '<span style="display:inline-block;background:#3b82f6;color:#fff;width:18px;height:18px;border-radius:4px;font-size:10px;text-align:center;line-height:18px;font-weight:700;margin-right:6px;vertical-align:middle" title="더바른사인">바</span>',
    "로켓출력공장": '<span style="display:inline-block;background:#a855f7;color:#fff;width:18px;height:18px;border-radius:4px;font-size:10px;text-align:center;line-height:18px;font-weight:700;margin-right:6px;vertical-align:middle" title="로켓출력공장">로</span>',
  };
  return map[mall] || '<span style="display:inline-block;background:#475569;color:#fff;width:18px;height:18px;border-radius:4px;font-size:10px;text-align:center;line-height:18px;font-weight:700;margin-right:6px;vertical-align:middle" title="-">?</span>';
}
function shortName(name){
  if (!name) return '';
  // 0. 직접 매칭 — 가장 정확한 카테고리부터
  // 1. 게시판 시리즈 (디자인/타입 + 게시판 + 사이즈)
  if (name.includes('게시판')) {
    const subs = ['슬림업','슬림디자인','강화유리','아크릴','알미늄','포켓','집게','꽂이','엘리베이터','승강기','학원','학교','어린이집','유치원','병원','사무실'];
    const found = subs.filter(s => name.includes(s)).slice(0, 2);
    const sizeMatch = name.match(/(\d+구|\d+칸|A4|B4|A3|B3)/);
    return [...found, '게시판', sizeMatch?.[0]].filter(Boolean).join(' ');
  }
  // 2. A형 입간판 (내용 + A형입간판)
  if (name.includes('A형 입간판') || name.includes('A형입간판')) {
    const subs = ['영업중','영업 중','OPEN','오픈','금연','주차금지','출입금지','오뚜기','금일휴업','휴무','외부차량','어서오세요','발렛','파킹','카페','식당','음식점','매장','병원','회의중','회의','휴업','노랑','블랙'];
    const found = subs.filter(s => name.includes(s)).slice(0, 2);
    return [...found, 'A형 입간판'].filter(Boolean).join(' ');
  }
  if (name.includes('입간판')) {
    const subs = ['영업중','오픈','금연','주차금지','오뚜기','외부차량','발렛','블랙','노랑','요일제','보호자','금일휴업','회의','학교'];
    const found = subs.filter(s => name.includes(s)).slice(0, 2);
    return [...found, '입간판'].filter(Boolean).join(' ');
  }
  // 3. 피난안내도
  if (name.includes('피난안내도') || name.includes('피난 안내도')) {
    const sz = name.match(/(B[345]|A[345]|\d+x\d+mm?)/);
    return ['피난안내도', sz?.[0]].filter(Boolean).join(' ');
  }
  // 4. 주차스티커 / 주차증
  if (name.includes('주차스티커') || name.includes('주차증')) {
    const subs = ['홀로그램','민무늬','원형','사각','패드형','반사지','입주민','100매','200매','300매','500매','뉴'];
    const found = subs.filter(s => name.includes(s)).slice(0, 2);
    return [...found, '주차스티커'].filter(Boolean).join(' ');
  }
  // 5. 스티커 (용도)
  if (name.includes('스티커')) {
    const types = [
      ['CCTV','CCTV'],['녹화중','녹화중'],['녹화','녹화중'],
      ['소방관진입','소방관진입창'],['소방대진입','소방대진입'],['소방','소방안전'],
      ['MSDS','MSDS'],['금연','금연'],['출입금지','출입금지'],
      ['방향유도','방향유도'],['방향 유도','방향유도'],['이동 방향','이동방향'],['이동방향','이동방향'],['진료 동선','진료동선'],['동선','동선'],
      ['단차','단차주의'],['미끄럼','미끄럼방지'],['홀로그램','홀로그램'],
      ['바닥','바닥'],['QR','QR'],['축광','축광야광'],['야광','야광'],
      ['주의','주의'],['경고','경고'],['위험','위험'],['안전','안전'],
      ['스승의날','스승의날'],['신년','신년'],['새해','새해'],
      ['엘리베이터','엘리베이터'],['승강기','승강기'],['주소','주소판'],['도로명','도로명']
    ];
    for (const [k, label] of types) {
      if (name.includes(k)) return label + ' 스티커';
    }
    // 사이즈만이라도
    const sz = name.match(/(\d+x\d+mm?)/);
    return sz ? `${sz[0]} 스티커` : '스티커';
  }
  // 6. 표지판/안내판/알림판/명패/팻말
  for (const cat of ['표지판','안내판','알림판','명패','팻말','푯말','간판']) {
    if (name.includes(cat)) {
      const sub = ['금연','주차','출입금지','CCTV','녹화','경고','주의','금지','매장','병원','학원','학교','어린이집','유치원','어린이','노약자','휠체어'];
      const found = sub.filter(s => name.includes(s)).slice(0, 1);
      const mat = ['아크릴','포맥스','시트','강화유리','알미늄'].filter(s => name.includes(s)).slice(0, 1);
      return [...mat, ...found, cat].filter(Boolean).join(' ');
    }
  }
  // 7. 현수막/배너
  if (name.includes('현수막') || name.includes('배너')) {
    const subs = ['오픈','축하','스승의날','신년','새해','구정','대형','어린이집','유치원','이벤트','졸업','입학','홍보','행사','골프','어버이날'];
    const found = subs.filter(s => name.includes(s)).slice(0, 2);
    return [...found, '현수막'].filter(Boolean).join(' ');
  }
  // 8. 실사출력 (재질 + 사이즈)
  if (name.includes('실사출력') || name.includes('포맥스') || name.includes('페트') || name.includes('시트지') || name.includes('PVC켈지') || name.includes('PET지') || name.includes('폼보드')) {
    const mat = ['포맥스','페트','PVC켈지','PET지','시트지','폼보드'].filter(s => name.includes(s))[0] || '실사출력';
    const sz = name.match(/(\d+cm이하|\d+x\d+|\d+T)/);
    return [mat, sz?.[0]].filter(Boolean).join(' ');
  }
  // 9. 수목표찰
  if (name.includes('수목표찰') || name.includes('기념식수') || name.includes('수목 표찰')) {
    return '수목표찰';
  }
  // 10. 도로명/번호판
  if (name.includes('도로명') || name.includes('번호판')) return '도로명 번호판';
  // 11. 바닥
  if (name.includes('바닥')) {
    const sub = ['미끄럼','마킹','글자','스텐실','경고','주의'];
    const found = sub.filter(s => name.includes(s)).slice(0,1);
    return [...found, '바닥'].filter(Boolean).join(' ');
  }
  // fallback: 처음 18자
  return name.length > 18 ? name.substring(0, 18) + '…' : name;
}function setupTable(tblId, tbodyId, data, isB){
  let sortKey = 'cost'; let sortDir = 'desc';
  function render(){
    const list = [...data].sort((a,b)=>{
      let va = a[sortKey]; let vb = b[sortKey];
      if (typeof va === 'string') return sortDir==='asc' ? va.localeCompare(vb,'ko') : vb.localeCompare(va,'ko');
      return sortDir==='asc' ? (va-vb) : (vb-va);
    });
    const maxCost = Math.max(...list.map(p=>p.cost)) || 1;
    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = list.map((p,i)=>{
      const w = Math.max(2, p.cost/maxCost*60);
      const ctrCls = p.ctr >= 1.0 ? 'green' : (p.ctr >= 0.5 ? '' : 'muted');
      if (isB) {
        return `<tr>
          <td class="muted">${i+1}</td>
          <td class="bold">${p.name||'-'}</td>
          <td class="muted">${p.campaign||'-'}</td>
          <td class="r bold"><span class="bar" style="width:${w}px"></span>${fmt(p.cost)}</td>
          <td class="r muted">${fmt(p.imp)}</td>
          <td class="r">${fmt(p.clk)}</td>
          <td class="r ${ctrCls}">${p.ctr.toFixed(2)}%</td>
        </tr>`;
      }
      const short = shortName(p.name);
      const mallTag = mallIcon(p.mall);
      const linked = p.url ? `<a href="${p.url}" target="_blank" title="${p.name.replace(/"/g,'&quot;')}">${short}</a>` : `<span title="${p.name.replace(/"/g,'&quot;')}">${short}</span>`;
      const nm = `${mallTag}${linked}`;
      const roasCls = p.roas >= 300 ? 'green' : (p.roas >= 100 ? '' : (p.roas > 0 ? 'yellow' : 'muted'));
      return `<tr>
        <td class="muted">${i+1}</td>
        <td class="bold">${nm}</td>
        <td class="r bold"><span class="bar" style="width:${w}px"></span>${fmt(p.cost)}</td>
        <td class="r muted">${fmt(p.imp)}</td>
        <td class="r">${fmt(p.clk)}</td>
        <td class="r ${ctrCls}">${p.ctr.toFixed(2)}%</td>
        <td class="r ${p.buy_v>0?'green':''}">${p.buy_v>0?fmt(p.buy_v):'-'}</td>
        <td class="r muted">${p.buy_n||'-'}</td>
        <td class="r ${p.cart_v>0?'yellow':''}">${p.cart_v>0?fmt(p.cart_v):'-'}</td>
        <td class="r ${roasCls}">${p.roas>0?p.roas.toFixed(1)+'%':'-'}</td>
        <td class="r muted">${p.camps}</td>
      </tr>`;
    }).join('');
    document.querySelectorAll('#'+tblId+' th').forEach(th=>{
      th.classList.remove('asc','desc');
      const s = th.querySelector('.sort'); if (s) s.textContent = '⇅';
      if (th.dataset.key === sortKey) {
        th.classList.add(sortDir);
        if (s) s.textContent = sortDir==='asc' ? '▲' : '▼';
      }
    });
  }
  document.querySelectorAll('#'+tblId+' th').forEach(th=>{
    th.addEventListener('click', ()=>{
      const k = th.dataset.key;
      if (!k || k==='rank') return;
      if (sortKey === k) sortDir = (sortDir==='asc'?'desc':'asc');
      else { sortKey = k; sortDir = 'desc'; }
      render();
    });
  });
  render();
}

setupTable('atbl','atb',D.products,false);
setupTable('btbl','btb',D.b_adgroups,true);

// 줄여도 될 광고 — overlay
function renderCutSection(areaId, title, color, list, cols){
  const area = document.getElementById(areaId);
  if (!area || !list || !list.length) {
    if (area) area.innerHTML = '<div style="padding:10px;color:var(--muted);font-size:11.5px;border-left:3px solid '+color+';background:#0f172a;border-radius:4px">'+title+' — 해당 없음</div>';
    return;
  }
  let html = '<div style="padding:12px;background:#0f172a;border-left:3px solid '+color+';border-radius:4px">';
  html += '<div style="color:'+color+';font-size:13px;font-weight:600;margin-bottom:8px">'+title+' ('+list.length+'개)</div>';
  html += '<table style="width:100%;border-collapse:collapse;font-size:11.5px"><thead><tr style="color:var(--muted);font-size:10.5px">';
  cols.forEach(c => { html += '<th style="text-align:'+(c.r?'right':'left')+';padding:4px">'+c.t+'</th>'; });
  html += '</tr></thead><tbody>';
  list.forEach((p,i) => {
    html += '<tr>';
    cols.forEach(c => {
      const v = c.fn(p, i);
      html += '<td style="padding:4px;text-align:'+(c.r?'right':'left')+';color:'+(c.color||'#fff')+'">'+v+'</td>';
    });
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  area.innerHTML = html;
}

// 3그룹 분류 표시
renderCutSection('cut_off_area',
  '✂ 명백히 OFF 가능 (광고비 ≥30,000원 & 매출 0 & 온라인 결제 카테고리) — 절감 약 '+fmt(D.cut.off_total)+'원',
  '#ef4444', D.cut.off,
  [
    {t:'#', fn:(p,i)=>(i+1), color:'#64748b'},
    {t:'카테고리', fn:p=>p.cat, color:'#94a3b8'},
    {t:'상품명', fn:p=>p.url?'<a href="'+p.url+'" target="_blank" style="color:#fff">'+(p.name||'').substring(0,50)+'</a>':(p.name||'').substring(0,50)},
    {t:'광고비', r:true, fn:p=>fmt(p.cost), color:'#fca5a5'},
    {t:'클릭', r:true, fn:p=>fmt(p.clk)},
    {t:'CTR', r:true, fn:p=>p.ctr.toFixed(2)+'%'},
  ]
);
renderCutSection('cut_low_ctr_area',
  '🔍 재검토 필요 — 전화 주문 가능 카테고리 (광고비 ≥30,000원 & 매출 0) — '+fmt(D.cut.review_total)+'원',
  '#f59e0b', D.cut.review,
  [
    {t:'#', fn:(p,i)=>(i+1), color:'#64748b'},
    {t:'카테고리', fn:p=>p.cat, color:'#fbbf24'},
    {t:'상품명', fn:p=>p.url?'<a href="'+p.url+'" target="_blank" style="color:#fff">'+(p.name||'').substring(0,50)+'</a>':(p.name||'').substring(0,50)},
    {t:'광고비', r:true, fn:p=>fmt(p.cost)},
    {t:'클릭', r:true, fn:p=>fmt(p.clk)},
    {t:'CTR', r:true, fn:p=>p.ctr.toFixed(2)+'%'},
    {t:'장바구니', r:true, fn:p=>p.cart_v>0?fmt(p.cart_v):'-', color:'#fbbf24'},
  ]
);
renderCutSection('cut_low_roas_area',
  '⚡ 확실히 줄일 — CTR 매우 낮음 (CTR <0.1% & 노출 ≥5,000) — 관심도 자체가 없음',
  '#a855f7', D.cut.clear,
  [
    {t:'#', fn:(p,i)=>(i+1), color:'#64748b'},
    {t:'카테고리', fn:p=>p.cat, color:'#94a3b8'},
    {t:'상품명', fn:p=>p.url?'<a href="'+p.url+'" target="_blank" style="color:#fff">'+(p.name||'').substring(0,50)+'</a>':(p.name||'').substring(0,50)},
    {t:'광고비', r:true, fn:p=>fmt(p.cost)},
    {t:'노출', r:true, fn:p=>fmt(p.imp)},
    {t:'클릭', r:true, fn:p=>fmt(p.clk)},
    {t:'CTR', r:true, fn:p=>p.ctr.toFixed(2)+'%', color:'#fca5a5'},
  ]
);
</script>
</body>
</html>
"""

WORKSPACE = os.environ.get("WORKSPACE_DIR", os.getcwd())
OUT = os.path.join(WORKSPACE, f"weekly_{START}_{END}.html")
open(OUT, "w", encoding="utf-8").write(html)
print(f"  [saved] {OUT} ({len(html):,}chars)", file=sys.stderr)

# GitHub Pages push
GH_PAT = os.environ.get("GITHUB_PAT","")
GH_OWNER = os.environ.get("GITHUB_OWNER","")
GH_REPO = os.environ.get("GITHUB_REPO","")
if GH_PAT and GH_OWNER and GH_REPO:
    def gh_put(path, content_bytes, msg):
        api = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
        sha = None
        try:
            req = urllib.request.Request(api, headers={"Authorization":f"Bearer {GH_PAT}","Accept":"application/vnd.github+json"})
            sha = json.loads(urllib.request.urlopen(req, context=ctx, timeout=15).read()).get("sha")
        except: pass
        body = {"message": msg, "content": base64.b64encode(content_bytes).decode()}
        if sha: body["sha"] = sha
        try:
            req = urllib.request.Request(api, data=json.dumps(body).encode(), method="PUT",
                headers={"Authorization":f"Bearer {GH_PAT}","Accept":"application/vnd.github+json","Content-Type":"application/json"})
            urllib.request.urlopen(req, context=ctx, timeout=20).read()
            return True
        except Exception as e:
            print(f"  GH push err {path}: {e}", file=sys.stderr); return False

    content = html.encode("utf-8")
    msg = f"weekly {START} ~ {END} ({DAYS_RANGE}d)"
    ok1 = gh_put(f"ceo-report/weekly-latest.html", content, msg)
    ok2 = gh_put(f"ceo-report/weekly/{END}.html", content, msg)
    if ok1: print(f"  [GH push] weekly-latest.html → https://{GH_OWNER}.github.io/{GH_REPO}/ceo-report/weekly-latest.html", file=sys.stderr)
