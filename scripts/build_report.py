#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
하나사인몰 대표보고용 광고 일일보고서 — 04-27 dashboard 양식 + 전일 데이터.

사용법:
  python3 build_report.py            # 어제 KST
  python3 build_report.py 2026-04-28 # 특정 날짜
"""
import csv, io, json, urllib.request, urllib.parse, hmac, hashlib, base64, time, sys, datetime, ssl, os
from collections import defaultdict

SHEET = "1Yuw_8we4nEzL1nslHI66LHBBE_uWc-ErALzhn2vvLGI"
A_KEY = os.environ["A_KEY"]
A_SEC = os.environ["A_SEC"]
A_CID = "1728536"
B_KEY = os.environ["B_KEY"]
B_SEC = os.environ["B_SEC"]
B_CID = "1558945"
N_BASE = "https://api.searchad.naver.com"
G_CID = os.environ.get("G_CID","8156547444")
G_MCC = os.environ.get("G_MCC","5192219711")
G_DEV = os.environ["G_DEV"]
G_OAUTH_C = os.environ["G_OAUTH_C"]
G_OAUTH_S = os.environ["G_OAUTH_S"]
G_REFRESH = os.environ["G_REFRESH"]

WORKSPACE = "/sessions/modest-gifted-euler/mnt/단순등록자동화"
if not os.path.isdir(WORKSPACE):
    WORKSPACE = os.environ.get("WORKSPACE_DIR", os.getcwd())

if len(sys.argv) > 1:
    TARGET = sys.argv[1]
else:
    kst = datetime.timezone(datetime.timedelta(hours=9))
    TARGET = (datetime.datetime.now(kst).date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
WEEKDAYS = ["월","화","수","목","금","토","일"]
dt = datetime.datetime.strptime(TARGET,"%Y-%m-%d")
WEEKDAY = WEEKDAYS[dt.weekday()]
GEN_AT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
print(f"[start] TARGET={TARGET} ({WEEKDAY})", file=sys.stderr)

ctx = ssl._create_unverified_context()

def to_int(s,d=0):
    try: return int(float((s or "0").replace(",","")))
    except: return d

def gviz_csv(g):
    if isinstance(g,int) or str(g).isdigit():
        url = f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&gid={g}"
    else:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(g)}"
    return list(csv.reader(io.StringIO(urllib.request.urlopen(url,context=ctx,timeout=30).read().decode("utf-8"))))

def n_sign(secret, m, p):
    ts = str(int(time.time()*1000))
    return ts, base64.b64encode(hmac.new(secret.encode(),f"{ts}.{m}.{p}".encode(),hashlib.sha256).digest()).decode()

def n_req(key, secret, cid, m, p, body=None):
    ts, sig = n_sign(secret, m, p.split("?")[0])
    H = {"X-Timestamp":ts,"X-API-KEY":key,"X-Customer":cid,"X-Signature":sig,"Content-Type":"application/json"}
    data = json.dumps(body).encode() if body else None
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(N_BASE+p,data=data,method=m,headers=H),context=ctx,timeout=20).read())
    except Exception as e: print(f"  N {m} {p} err: {e}",file=sys.stderr); return None

def n_stat(key, secret, cid, reportTp, max_wait=120):
    rsp = n_req(key,secret,cid,"POST","/stat-reports",{"reportTp":reportTp,"statDt":TARGET})
    if not rsp: return None
    rid = rsp.get("reportJobId") or rsp.get("id")
    if not rid: return None
    t0 = time.time()
    while time.time()-t0 < max_wait:
        time.sleep(2)
        info = n_req(key,secret,cid,"GET",f"/stat-reports/{rid}")
        if not info: continue
        st = info.get("status")
        if st in ("BUILT","REGISTERED","DONE"):
            durl = info.get("downloadUrl")
            if durl:
                ts2,sig2 = n_sign(secret,"GET",urllib.parse.urlparse(durl).path)
                req2 = urllib.request.Request(durl,headers={"X-Timestamp":ts2,"X-API-KEY":key,"X-Customer":cid,"X-Signature":sig2})
                try: return urllib.request.urlopen(req2,context=ctx,timeout=30).read().decode("utf-8","ignore")
                except: return None
        if st in ("FAILED","EXPIRED","NONE"): return None
    return None


# === A 데이터 === #
print("[1] A", file=sys.stderr)
def _mall_of(u):
    if not u: return ""
    if "/hanasign/" in u: return "하나몰"
    if "/thecorrectsign/" in u: return "더바른사인"
    if "/rocketprinting/" in u: return "로켓출력공장"
    return ""

mp = {}
try:
    for r in gviz_csv(1248602534)[1:]:
        if not r or not r[0]: continue
        pid = r[0].strip()
        name = r[1].strip() if len(r)>1 else ""
        pno = r[3].strip() if len(r)>3 else ""
        # 매핑 시트의 "스마트스토어상품번호" 컬럼은 이미 풀 URL일 수도, 숫자 ID일 수도 있음
        if pno.startswith("http"):
            url = pno
        elif pno:
            url = f"https://smartstore.naver.com/hanasign/products/{pno}"
        else:
            url = ""
        mp[pid] = {"name":name, "url":url, "mall": _mall_of(url)}
except: pass

all_rows = []
buy_map = {}
# A는 항상 API 직접 호출 (시트 캐시 시점 차이 제거)
print("  [A API 직접 호출]", file=sys.stderr)
a_camps_api = n_req(A_KEY,A_SEC,A_CID,"GET","/ncc/campaigns") or []
a_cidx = {c["nccCampaignId"]:c["name"] for c in a_camps_api if isinstance(c,dict)}
a_adgs_api = n_req(A_KEY,A_SEC,A_CID,"GET","/ncc/adgroups") or []
a_aidx = {a["nccAdgroupId"]:a["name"] for a in a_adgs_api if isinstance(a,dict)}
tsv = n_stat(A_KEY,A_SEC,A_CID,"AD")
if tsv:
    for line in tsv.splitlines():
        cols = line.split("\t")
        if len(cols)<12: continue
        try:
            imp = int(float(cols[-5].replace(",","")))
            clk = int(float(cols[-4].replace(",","")))
            cost = int(float(cols[-3].replace(",","")))
        except: imp=clk=cost=0
        cid=cols[2]; agid=cols[3]; pid=cols[5] if len(cols)>5 else ""
        all_rows.append({"campaign":a_cidx.get(cid,cid),"adgroup":a_aidx.get(agid,agid),"pid":pid,
                         "imp":imp,"clk":clk,"cost":cost,
                         "name":mp.get(pid,{}).get("name",pid),"url":mp.get(pid,{}).get("url","")})
tsv = n_stat(A_KEY,A_SEC,A_CID,"AD_CONVERSION")
if tsv:
    for line in tsv.splitlines():
        cols = line.split("\t")
        if len(cols)<13: continue
        try:
            pid=cols[5]; ctype=cols[10]
            cnt=int(float(cols[11].replace(",",""))); val=int(float(cols[12].replace(",","")))
        except: continue
        if pid not in buy_map:
            buy_map[pid]={"buy_n":0,"buy_v":0,"d_buy_n":0,"d_buy_v":0,"i_buy_n":0,"i_buy_v":0,"cart_n":0,"cart_v":0}
        if ctype=="purchase":
            buy_map[pid]["buy_n"]+=cnt; buy_map[pid]["buy_v"]+=val
            buy_map[pid]["i_buy_n"]+=cnt; buy_map[pid]["i_buy_v"]+=val
        elif ctype=="add_to_cart":
            buy_map[pid]["cart_n"]+=cnt; buy_map[pid]["cart_v"]+=val

# A all_rows dedupe — 네이버 stat report(reportTp=AD)가 같은 광고를 키워드/매체/디바이스별로 분할 반환.
# 같은 PID가 한 그룹 안에서 수백 행으로 등장하는 이슈 대응 (2026-05-18 차장 지시).
# 효과: 소재수 / TOP cost / TOP click / 비전환 items 표시에서 PID 중복 제거.
# 광고비·매출·ROAS 합계 불변(분할된 cost를 합산해서 보존).
_a_raw_count = len(all_rows)
_dedup = {}
for r in all_rows:
    k = (r["pid"], r["campaign"], r["adgroup"])
    if k not in _dedup:
        _dedup[k] = {**r}
    else:
        _dedup[k]["imp"] += r["imp"]
        _dedup[k]["clk"] += r["clk"]
        _dedup[k]["cost"] += r["cost"]
all_rows = list(_dedup.values())
print(f"  A dedupe: raw {_a_raw_count} → unique {len(all_rows)} rows", file=sys.stderr)

# === ADVoost 데이터 합산 (콘솔과 일치) === #
# 2026-05-18 차장 지시: CSV stale(5/7 데이터 11일째 합산) 이슈로 일시 제외.
# 재개 조건: ADVoost CSV에 일자 컬럼 포함 형식으로 다운로드 가능 확인 후 ADVOOST_ENABLED=True
ADVOOST_ENABLED = False
advoost = {"cost":0,"imp":0,"clk":0,"rows":0}
ADV_PATHS = [
    os.path.join(WORKSPACE, "애드부스트", "result.csv"),
    os.path.join(os.path.dirname(__file__), "advoost.csv"),  # GitHub Actions용
]
if ADVOOST_ENABLED:
    for ap in ADV_PATHS:
        if not os.path.exists(ap): continue
        try:
            with open(ap, encoding='utf-8-sig') as f:
                rdr = csv.reader(f)
                hdr = next(rdr)
                ic = hdr.index('총비용') if '총비용' in hdr else -1
                ii = hdr.index('노출수') if '노출수' in hdr else -1
                il = hdr.index('클릭수') if '클릭수' in hdr else -1
                for r in rdr:
                    if ic>=0 and len(r)>ic: advoost["cost"] += to_int(r[ic])
                    if ii>=0 and len(r)>ii: advoost["imp"] += to_int(r[ii])
                    if il>=0 and len(r)>il: advoost["clk"] += to_int(r[il])
                    advoost["rows"] += 1
            print(f"  ADVoost: cost={advoost['cost']:,} imp={advoost['imp']:,} clk={advoost['clk']} ({advoost['rows']}행)", file=sys.stderr)
            break
        except Exception as e:
            print(f"  ADVoost {ap} err: {e}", file=sys.stderr)
    if advoost["rows"]==0:
        print("  ADVoost: 데이터 없음 (CSV 미입력)", file=sys.stderr)
else:
    print("  ADVoost: 비활성화 (ADVOOST_ENABLED=False, 2026-05-18 차장 지시)", file=sys.stderr)

a_total = {"imp":sum(r["imp"] for r in all_rows)+advoost["imp"],
           "clk":sum(r["clk"] for r in all_rows)+advoost["clk"],
           "cost":sum(r["cost"] for r in all_rows)+advoost["cost"],
           "count":len(all_rows),
           "advoost":advoost}
camp_agg = defaultdict(lambda:{"cost":0,"clk":0,"imp":0})
for r in all_rows:
    c=camp_agg[r["campaign"]]; c["cost"]+=r["cost"]; c["clk"]+=r["clk"]; c["imp"]+=r["imp"]
a_campaigns = sorted([{"name":k or "(미상)",**v} for k,v in camp_agg.items()], key=lambda x:-x["cost"])
# 상품명 단위 합산 헬퍼 — 같은 상품을 여러 캠페인/광고그룹에 등록한 케이스 묶음 (2026-05-18 차장 지시)
def _by_name(rows):
    agg = {}
    for _r in rows:
        _k = (_r.get("name") or _r["pid"]).strip() or _r["pid"]
        if _k not in agg:
            agg[_k] = {**_r}
            agg[_k]["_camps"] = {_r["campaign"]} if _r.get("campaign") else set()
            agg[_k]["_grps"] = {_r["adgroup"]} if _r.get("adgroup") else set()
            agg[_k]["_pids"] = {_r["pid"]} if _r.get("pid") else set()
        else:
            agg[_k]["imp"] += _r["imp"]
            agg[_k]["clk"] += _r["clk"]
            agg[_k]["cost"] += _r["cost"]
            if _r.get("campaign"): agg[_k]["_camps"].add(_r["campaign"])
            if _r.get("adgroup"): agg[_k]["_grps"].add(_r["adgroup"])
            if _r.get("pid"): agg[_k]["_pids"].add(_r["pid"])
    out = []
    for v in agg.values():
        v["_camps"] = sorted(v["_camps"])
        v["_grps"] = sorted(v["_grps"])
        v["_pids"] = sorted(v["_pids"])
        v["_split_count"] = len(v["_pids"])  # 몇 개 별도 광고로 분산됐는지
        out.append(v)
    return out

top_cost = sorted(_by_name(all_rows), key=lambda x:-x["cost"])[:20]
top_click = sorted(_by_name(all_rows), key=lambda x:-x["clk"])[:20]

a_buy_total={"n":0,"v":0,"d_n":0,"d_v":0,"i_n":0,"i_v":0}
a_cart_total={"n":0,"v":0}
a_buy_list=[]; a_cart_list=[]
pid_first = {r["pid"]:r for r in all_rows if r["pid"]}
for pid, b in buy_map.items():
    info=pid_first.get(pid,{})
    item={"pid":pid,**b,"name":info.get("name",mp.get(pid,{}).get("name",pid)),
          "url":info.get("url",mp.get(pid,{}).get("url","")),
          "store": mp.get(pid,{}).get("mall","") or "하나몰"}
    if b["buy_n"]>0:
        a_buy_list.append(item)
        a_buy_total["n"]+=b["buy_n"]; a_buy_total["v"]+=b["buy_v"]
        a_buy_total["d_n"]+=b["d_buy_n"]; a_buy_total["d_v"]+=b["d_buy_v"]
        a_buy_total["i_n"]+=b["i_buy_n"]; a_buy_total["i_v"]+=b["i_buy_v"]
    if b["cart_n"]>0:
        a_cart_list.append(item)
        a_cart_total["n"]+=b["cart_n"]; a_cart_total["v"]+=b["cart_v"]
a_buy_list.sort(key=lambda x:-x["buy_v"])
a_cart_list.sort(key=lambda x:-x["cart_v"])

grp=defaultdict(lambda:{"cost":0,"clk":0,"imp":0,"count":0,"items":[],"rev":0})
for r in all_rows:
    g=r["adgroup"] or "(미상)"
    grp[g]["cost"]+=r["cost"]; grp[g]["clk"]+=r["clk"]; grp[g]["imp"]+=r["imp"]
    grp[g]["count"]+=1; grp[g]["items"].append(r)
    grp[g]["rev"]+=buy_map.get(r["pid"],{}).get("buy_v",0)
_ncg_list = []
for _k, _v in grp.items():
    if _v["cost"]>0 and _v["rev"]==0:
        _items_named = _by_name(_v["items"])
        _items_named.sort(key=lambda x:-x["cost"])
        _ncg_list.append({"name":_k,"cost":_v["cost"],"clk":_v["clk"],"imp":_v["imp"],
                          "count":len(_items_named),"items":_items_named[:10]})
no_conv_groups = sorted(_ncg_list, key=lambda x:-x["cost"])

# === click_no_buy — 클릭 있고 매출 0 상품 (상품명 단위 합산, TOP 20) ===
# 차장님 요구 (2026-05-18): 오늘 클릭됐는데 아직 구매 전인 상품을 한 눈에 보여주기
# 데이터 소스: all_rows + buy_map. 상품명 단위로 묶고 클릭순 정렬
_buy_v_by_pid = {pid: b["buy_v"] for pid, b in buy_map.items() if b.get("buy_v",0) > 0}
_cnb = {}
for r in all_rows:
    if r.get("clk", 0) <= 0: continue
    if r.get("pid","") in _buy_v_by_pid: continue
    key = (r.get("name") or r["pid"]).strip() or r["pid"]
    if key not in _cnb:
        _cnb[key] = {"name": key, "url": r.get("url",""),
                     "clk":0, "cost":0, "imp":0,
                     "_pids":set(), "_camps":set(), "_grps":set()}
    c = _cnb[key]
    c["clk"] += r["clk"]; c["cost"] += r["cost"]; c["imp"] += r["imp"]
    c["_pids"].add(r.get("pid",""))
    c["_camps"].add(r.get("campaign",""))
    c["_grps"].add(r.get("adgroup",""))
click_no_buy = []
for v in _cnb.values():
    click_no_buy.append({
        "name": v["name"], "url": v["url"],
        "clk": v["clk"], "cost": v["cost"], "imp": v["imp"],
        "camps": sorted(v["_camps"]), "grps": sorted(v["_grps"]),
        "pid_count": len(v["_pids"]),
    })
click_no_buy.sort(key=lambda x: (-x["clk"], -x["cost"]))
click_no_buy_top = click_no_buy[:20]
click_no_buy_total = {
    "count": len(click_no_buy),
    "clk_sum": sum(c["clk"] for c in click_no_buy),
    "cost_sum": sum(c["cost"] for c in click_no_buy),
}
print(f"  click_no_buy: {len(click_no_buy)}개 상품 / 클릭 {click_no_buy_total['clk_sum']:,} / 광고비 {click_no_buy_total['cost_sum']:,}", file=sys.stderr)
no_conv_total = sum(g["cost"] for g in no_conv_groups)
no_conv_pct = round(no_conv_total/a_total["cost"]*100,1) if a_total["cost"] else 0
a_roas = round(a_buy_total["v"]/a_total["cost"]*100,1) if a_total["cost"] else 0
cart_roas = round((a_buy_total["v"]+a_cart_total["v"])/a_total["cost"]*100,1) if a_total["cost"] else 0
direct_pct = round(a_buy_total["d_v"]/a_buy_total["v"]*100,1) if a_buy_total["v"] else 0
indirect_pct = round(a_buy_total["i_v"]/a_buy_total["v"]*100,1) if a_buy_total["v"] else 0

print(f"  A 광고비={a_total['cost']:,} 매출={a_buy_total['v']:,}", file=sys.stderr)


# === B 데이터 === #
print("[2] B", file=sys.stderr)
b_camps_api = n_req(B_KEY,B_SEC,B_CID,"GET","/ncc/campaigns") or []
b_cidx = {c["nccCampaignId"]:c["name"] for c in b_camps_api if isinstance(c,dict)}
b_camp_active = defaultdict(int)
b_adgs_api = n_req(B_KEY,B_SEC,B_CID,"GET","/ncc/adgroups") or []
b_aidx = {a["nccAdgroupId"]:{"name":a["name"],"cid":a.get("nccCampaignId"),"status":a.get("status","")} for a in b_adgs_api if isinstance(a,dict)}
for ag in b_aidx.values():
    b_camp_active[ag.get("cid")] += 1

# 광고그룹별 광고 헤드라인+랜딩URL 매핑
b_ad_text = {}
for _agid in b_aidx.keys():
    try:
        _ads = n_req(B_KEY,B_SEC,B_CID,"GET",f"/ncc/ads?nccAdgroupId={_agid}") or []
        if not _ads: continue
        _chosen = next((a for a in _ads if a.get("status")=="ELIGIBLE"), _ads[0])
        _ad = _chosen.get("ad", {}) or {}
        _hl = _ad.get("headline","") or ""
        _url = ((_ad.get("pc",{}) or {}).get("final","") or
                (_ad.get("mobile",{}) or {}).get("final","") or "")
        if _hl or _url:
            b_ad_text[_agid] = {"headline": _hl, "url": _url}
    except Exception as _e:
        pass
print(f"  광고헤드라인 매핑: {len(b_ad_text)}개", file=sys.stderr)

b_total = {"imp":0,"clk":0,"cost":0,"count":0}
b_camp_agg = defaultdict(lambda:{"cost":0,"clk":0,"imp":0,"name":"","cid":""})
b_adg_agg = defaultdict(lambda:{"cost":0,"clk":0,"imp":0,"name":"","campaign":"","cid":""})
tsv = n_stat(B_KEY,B_SEC,B_CID,"AD")
if tsv:
    for line in tsv.splitlines():
        cols = line.split("\t")
        if len(cols)<12: continue
        try:
            imp = int(float(cols[-5].replace(",","")))
            clk = int(float(cols[-4].replace(",","")))
            cost = int(float(cols[-3].replace(",","")))
        except: imp=clk=cost=0
        cid=cols[2]; agid=cols[3]
        b_total["imp"]+=imp; b_total["clk"]+=clk; b_total["cost"]+=cost; b_total["count"]+=1
        if cid in b_cidx:
            x=b_camp_agg[cid]; x["name"]=b_cidx[cid]; x["cid"]=cid
            x["cost"]+=cost; x["clk"]+=clk; x["imp"]+=imp
        if agid in b_aidx:
            x=b_adg_agg[agid]; x["name"]=b_aidx[agid]["name"]
            x["campaign"]=b_cidx.get(b_aidx[agid]["cid"],""); x["cid"]=b_aidx[agid]["cid"]
            x["cost"]+=cost; x["clk"]+=clk; x["imp"]+=imp
            _at = b_ad_text.get(agid, {})
            x["headline"] = _at.get("headline","")
            x["url"] = _at.get("url","")
b_camps = sorted([{**v} for v in b_camp_agg.values()], key=lambda x:-x["cost"])
b_adgs = sorted([{**v} for v in b_adg_agg.values()], key=lambda x:-x["cost"])

b_conv = {"n":0,"v":0}
tsv = n_stat(B_KEY,B_SEC,B_CID,"AD_CONVERSION")
if tsv:
    for line in tsv.splitlines():
        cols = line.split("\t")
        if len(cols)<13: continue
        try:
            ctype=cols[10]; cnt=int(float(cols[11].replace(",",""))); val=int(float(cols[12].replace(",","")))
        except: continue
        if ctype=="purchase":
            b_conv["n"]+=cnt; b_conv["v"]+=val
b_roas = round(b_conv["v"]/b_total["cost"]*100,1) if b_total["cost"] else 0
b_ctr = round(b_total["clk"]/b_total["imp"]*100,2) if b_total["imp"] else 0
b_cpc = round(b_total["cost"]/b_total["clk"]) if b_total["clk"] else 0
print(f"  B 광고비={b_total['cost']:,} 매출={b_conv['v']:,}", file=sys.stderr)


# === G 데이터 === #
print("[3] Google Ads", file=sys.stderr)
g_total = {"cost":0,"clk":0,"imp":0,"conv":0}
g_camps=[]; g_search_terms=[]; g_trend=[]; g_devices={}; g_buy={"n":0,"v":0}
try:
    body = urllib.parse.urlencode({"client_id":G_OAUTH_C,"client_secret":G_OAUTH_S,
                                    "refresh_token":G_REFRESH,"grant_type":"refresh_token"}).encode()
    g_tok = json.loads(urllib.request.urlopen(
        urllib.request.Request("https://oauth2.googleapis.com/token",data=body,method="POST",
                               headers={"Content-Type":"application/x-www-form-urlencoded"}),
        context=ctx,timeout=20).read())["access_token"]
except Exception as e:
    print(f"  OAuth FAIL: {e}", file=sys.stderr); g_tok=None

def gq(query):
    if not g_tok: return None
    try:
        return json.loads(urllib.request.urlopen(
            urllib.request.Request(f"https://googleads.googleapis.com/v20/customers/{G_CID}/googleAds:searchStream",
                                    data=json.dumps({"query":query}).encode(),method="POST",
                                    headers={"Authorization":f"Bearer {g_tok}","developer-token":G_DEV,
                                             "login-customer-id":G_MCC,"Content-Type":"application/json"}),
            context=ctx,timeout=30).read().decode())
    except Exception as e:
        print(f"  GAQL err: {e}", file=sys.stderr); return None

if g_tok:
    rsp = gq(f"SELECT campaign.id,campaign.name,metrics.cost_micros,metrics.clicks,metrics.impressions,metrics.conversions FROM campaign WHERE segments.date='{TARGET}'")
    for ch in rsp or []:
        for row in ch.get("results",[]):
            m=row.get("metrics",{})
            cost=int(m.get("costMicros","0"))//1000000
            g_camps.append({"name":row["campaign"]["name"],"cost":cost,"clk":int(m.get("clicks","0")),
                            "imp":int(m.get("impressions","0")),"conv":float(m.get("conversions",0))})
            g_total["cost"]+=cost; g_total["clk"]+=int(m.get("clicks","0"))
            g_total["imp"]+=int(m.get("impressions","0")); g_total["conv"]+=float(m.get("conversions",0))
    rsp = gq(f"SELECT segments.conversion_action_name,metrics.all_conversions,metrics.all_conversions_value FROM customer WHERE segments.date='{TARGET}'")
    for ch in rsp or []:
        for row in ch.get("results",[]):
            act=row["segments"]["conversionActionName"]; m=row["metrics"]
            if "구매" in act or "urchase" in act:
                g_buy["v"]+=int(float(m.get("allConversionsValue",0)))
                g_buy["n"]+=int(float(m.get("allConversions",0)))
    rsp = gq(f"SELECT search_term_view.search_term, ad_group.name, "
             f"segments.keyword.info.text, segments.search_term_match_type, "
             f"metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.impressions "
             f"FROM search_term_view WHERE segments.date='{TARGET}' "
             f"ORDER BY metrics.cost_micros DESC LIMIT 10")
    _mt_label = {"EXACT":"정확매칭","PHRASE":"구문매칭","BROAD":"확장매칭","NEAR_EXACT":"유사매칭","NEAR_PHRASE":"유사구문"}
    for ch in rsp or []:
        for row in ch.get("results",[]):
            m=row["metrics"]
            seg = row.get("segments",{}) or {}
            mt = seg.get("searchTermMatchType","") or ""
            kw = (seg.get("keyword",{}) or {}).get("info",{}).get("text","") or ""
            g_search_terms.append({
                "term":row["searchTermView"]["searchTerm"],
                "adgroup":row["adGroup"]["name"],
                "clk":int(m.get("clicks","0")),"cost":int(m.get("costMicros","0"))//1000000,
                "conv":float(m.get("conversions",0)),
                "imp":int(m.get("impressions","0")),
                "match_type":mt,
                "match_label":_mt_label.get(mt, mt),
                "matched_kw":kw,
            })
    rsp = gq(f"SELECT segments.device,metrics.cost_micros,metrics.clicks FROM customer WHERE segments.date='{TARGET}'")
    for ch in rsp or []:
        for row in ch.get("results",[]):
            d=row["segments"]["device"]; m=row["metrics"]
            g_devices[d]={"cost":int(m.get("costMicros","0"))//1000000,"clk":int(m.get("clicks","0"))}
    end_d = datetime.datetime.strptime(TARGET,"%Y-%m-%d").date()
    start_d = end_d - datetime.timedelta(days=7)
    rsp = gq(f"SELECT segments.date,metrics.cost_micros,metrics.clicks,metrics.conversions FROM campaign WHERE segments.date BETWEEN '{start_d}' AND '{end_d}'")
    if rsp:
        agg=defaultdict(lambda:{"cost":0,"clk":0,"conv":0})
        for ch in rsp:
            for row in ch.get("results",[]):
                d=row["segments"]["date"]; m=row["metrics"]
                agg[d]["cost"]+=int(m.get("costMicros","0"))//1000000
                agg[d]["clk"]+=int(m.get("clicks","0"))
                agg[d]["conv"]+=float(m.get("conversions",0))
        g_trend=[{"date":k,**v} for k,v in sorted(agg.items())]

    # === 구글애즈 키워드별 final_urls 수집 (2026-05-18 차장 지시 후 수정) ===
    # 차장님이 키워드(ad_group_criterion) 단위로 final_url을 다르게 설정 → keyword_view로 조회
    g_kw_url = {}    # keyword text → url
    g_kw_cost = {}   # keyword text → cost (캠페인 대표 URL 산정용)
    g_kw_camp = {}   # keyword text → campaign name
    rsp = gq(f"SELECT campaign.name, ad_group.name, "
             f"ad_group_criterion.keyword.text, ad_group_criterion.final_urls, "
             f"metrics.cost_micros FROM keyword_view "
             f"WHERE segments.date='{TARGET}'")
    for ch in rsp or []:
        for row in ch.get("results",[]):
            crit = row.get("adGroupCriterion",{}) or {}
            kw = (crit.get("keyword",{}) or {}).get("text","")
            urls = crit.get("finalUrls") or []
            cost = int(row.get("metrics",{}).get("costMicros","0"))//1000000
            cn = row.get("campaign",{}).get("name","")
            if kw and urls:
                # 같은 키워드가 여러 광고그룹에 있으면 cost 큰 쪽 채택
                if kw not in g_kw_cost or cost > g_kw_cost[kw]:
                    g_kw_url[kw] = urls[0]
                    g_kw_cost[kw] = cost
                    g_kw_camp[kw] = cn

    # 캠페인 대표 URL = 그 캠페인 내 광고비 1등 키워드의 URL
    g_camp_url = {}
    _camp_best = {}
    for kw, url in g_kw_url.items():
        cn = g_kw_camp.get(kw,"")
        cost = g_kw_cost.get(kw,0)
        if not cn: continue
        if cn not in _camp_best or cost > _camp_best[cn][0]:
            _camp_best[cn] = (cost, url)
    for cn, (cost, url) in _camp_best.items():
        g_camp_url[cn] = url

    print(f"  G URL 매핑: 캠페인 {len(g_camp_url)}개, 키워드 {len(g_kw_url)}개", file=sys.stderr)

    # 검색어 표 — 매칭된 키워드의 URL 사용
    # search_term_view에 매칭 키워드를 받으려면 별도 쿼리 필요 → 검색어 text가 키워드와 동일/포함일 때 매핑
    for c in g_camps:
        c["url"] = g_camp_url.get(c["name"], "")
    for t in g_search_terms:
        term = (t.get("term") or "").strip()
        mkw = (t.get("matched_kw") or "").strip()
        # 1차: search_term_view가 알려준 매칭 키워드 직접 사용 (가장 정확)
        url = g_kw_url.get(mkw, "") if mkw else ""
        # 2차: 검색어와 정확히 같은 키워드
        if not url:
            url = g_kw_url.get(term, "")
        # 3차: 부분 매칭
        if not url:
            for kw, _u in g_kw_url.items():
                if kw and (kw in term or term in kw):
                    url = _u; break
        # 4차: 캠페인 대표
        if not url:
            url = g_camp_url.get("기본웹트래픽","")
        t["url"] = url
        t["url_kw"] = mkw or term  # 표시용 — 어느 키워드 URL 매핑됐는지

    # D 객체에 키워드 단위 데이터도 노출 (디버그/추가 표시용)
    g_keywords_top = sorted(
        [{"text":k,"url":g_kw_url[k],"cost":g_kw_cost.get(k,0),"campaign":g_kw_camp.get(k,"")}
         for k in g_kw_url], key=lambda x:-x["cost"])[:20]

g_ctr = round(g_total["clk"]/g_total["imp"]*100,2) if g_total["imp"] else 0
g_cpc = round(g_total["cost"]/g_total["clk"]) if g_total["clk"] else 0
g_roas = round(g_buy["v"]/g_total["cost"]*100,1) if g_total["cost"] else 0
print(f"  G 광고비={g_total['cost']:,} 매출={g_buy['v']:,}", file=sys.stderr)


# === D 객체 === #
total_combined_cost = a_total["cost"]+b_total["cost"]+g_total["cost"]
b_share = round(b_total["cost"]/total_combined_cost*100,1) if total_combined_cost else 0
combined = {"imp":a_total["imp"]+b_total["imp"]+g_total["imp"],
            "clk":a_total["clk"]+b_total["clk"]+g_total["clk"],
            "cost":total_combined_cost,
            "buy_v":a_buy_total["v"]+b_conv["v"]+g_buy["v"]}
combined["roas"]=round(combined["buy_v"]/combined["cost"]*100,1) if combined["cost"] else 0

D = {
    "meta":{"date":TARGET,"weekday":WEEKDAY,"generated_at":GEN_AT,
            "roas":a_roas,"cart_roas":cart_roas,
            "no_conv_cost":no_conv_total,"no_conv_pct":no_conv_pct,"no_conv_count":len(no_conv_groups)},
    "total":a_total,
    "top_cost":top_cost,"top_click":top_click,
    "campaigns":a_campaigns,
    "cart":a_cart_list,"cart_total":a_cart_total,
    "buy":a_buy_list,"buy_total":a_buy_total,
    "all_rows":all_rows,
    "report":{"top_revenue":a_buy_list[:5],"no_conv_cost":no_conv_total,"no_conv_pct":no_conv_pct,
              "no_conv_count":len(no_conv_groups),"direct_pct":direct_pct,"indirect_pct":indirect_pct},
    "no_conv_groups":no_conv_groups,
    "no_conv_total":no_conv_total,
    "click_no_buy": click_no_buy_top,
    "click_no_buy_total": click_no_buy_total,
    "naver_b":{"total":b_total,"campaigns":b_camps,"adgroups":b_adgs,
               "active_per_camp":dict(b_camp_active),
               "ctr":b_ctr,"cpc":b_cpc,"roas":b_roas,"share_pct":b_share},
    "b_conv":b_conv,
    "google":{"total":g_total,"buy_v":g_buy["v"],"buy_n":g_buy["n"],
              "campaigns":g_camps,"devices":g_devices,
              "search_terms":g_search_terms,"trend":g_trend,
              "keywords_top": g_keywords_top if 'g_keywords_top' in dir() else [],
              "ctr":g_ctr,"cpc":g_cpc,"roas":g_roas},
    "device_a":{"M":{"imp":0,"clk":0,"cost":0},"P":{"imp":0,"clk":0,"cost":0}},
    "hour_a":{f"{h:02d}":{"imp":0,"clk":0,"cost":0} for h in range(24)},
    "combined":combined,
}


# === HTML 빌드 === #
print("[4] HTML 빌드", file=sys.stderr)
TEMPLATE = os.path.join(WORKSPACE, "네이버광고_1차보고대시보드_2026-04-27.html")
if not os.path.exists(TEMPLATE):
    TEMPLATE = os.path.join(WORKSPACE, "template_2026-04-27.html")
src = open(TEMPLATE).read()

# 1차 시안 상태 pill + 참고 안내 박스 삭제 (3매체 LIVE 이후 불필요)
import re as _re
src = _re.sub(
    r'<div class="row1">\s*<span class="pill draft">📋 1차 시안</span>.*?</div>\s*',
    '', src, flags=_re.DOTALL
)
src = _re.sub(
    r'<div class="notice">\s*⚠\s*<span><b>참고</b>.*?</div>\s*',
    '', src, flags=_re.DOTALL
)

s = src.find("const D = ")
depth, i, end = 0, s+10, -1
while i < len(src):
    c = src[i]
    if c=="{": depth+=1
    elif c=="}":
        depth-=1
        if depth==0: end=i+1; break
    i+=1
new_src = src[:s+10] + json.dumps(D, ensure_ascii=False) + src[end:]

date_dot = TARGET.replace("-",".")
mm = TARGET.split("-")[1]; dd = TARGET.split("-")[2]
new_src = new_src.replace("2026-04-27 (월)", f"{TARGET} ({WEEKDAY})")
new_src = new_src.replace("2026-04-27", TARGET)
new_src = new_src.replace("2026.04.27", date_dot)
new_src = new_src.replace("04월 27일", f"{mm}월 {dd}일")
new_src = new_src.replace(" (월) ", f" ({WEEKDAY}) ")
new_src = new_src.replace(">월요일<", f">{WEEKDAY}요일<")
new_src = new_src.replace("월요일", f"{WEEKDAY}요일")
new_src = new_src.replace("(04-20~04-27)", f"(8일 추이 ~{TARGET})")

# JS Overlay
overlay_js = """
<script>
(function(){
  function fmtN(n){return Number(n||0).toLocaleString('ko-KR');}
  function ratio2(a,b){return b>0?(a/b*100).toFixed(2)+'%':'-';}
  function ratio1(a,b){return b>0?(a/b*100).toFixed(1)+'%':'0.0%';}
  function roundCpc(c,k){return k>0?Math.round(c/k):0;}
  function _init_overlays(){
    try { overlayHeader(); } catch(e){ console.error('overlayHeader',e); }
    try { overlayNoConv(); } catch(e){ console.error('overlayNoConv',e); }
    try { overlayB(); } catch(e){ console.error('overlayB',e); }
    try { overlayG(); } catch(e){ console.error('overlayG',e); }
    try { overlayClickNoBuy(); } catch(e){ console.error('overlayClickNoBuy',e); }
    try { hideDirectIndirectCols(); } catch(e){ console.error('hideDirectIndirect',e); }
    try { placeholderizeStaticCards(); } catch(e){ console.error('placeholderize',e); }
    try { expandSlotsIfNeeded(); } catch(e){ console.error('expandSlots',e); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init_overlays);
  } else {
    _init_overlays();
  }
  function escapeHtml(s){
    return String(s||'').replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function linkify(name, url){
    var n = escapeHtml(name);
    return url ? '<a href="'+escapeHtml(url)+'" target="_blank" rel="noopener" style="color:inherit;border-bottom:1px dotted rgba(255,255,255,0.3)">'+n+'</a>' : n;
  }
  function overlayNoConv(){
    var groups = D.no_conv_groups||[];
    // 헤더 행 (gh data-tgt="g_noconv-N")
    var ghs = document.querySelectorAll('tr.gh[data-tgt^="g_noconv-"]');
    ghs.forEach(function(row, idx){
      if(idx >= groups.length){
        row.style.display='none';
        var gd = document.getElementById('g_noconv-'+idx);
        if(gd) gd.style.display='none';
        return;
      }
      var g = groups[idx];
      var tds = row.querySelectorAll('td');
      // # / 상품군 / 소재수 / 클릭 / 광고비
      if(tds[1]) tds[1].textContent = g.name || '';
      if(tds[2]) tds[2].textContent = fmtN(g.count||0);
      if(tds[3]) tds[3].textContent = fmtN(g.clk||0);
      if(tds[4]){
        // bar + 광고비 + arrow 유지
        var bar = tds[4].querySelector('.bar');
        var arr = tds[4].querySelector('.arr');
        var barHtml = bar ? bar.outerHTML : '';
        var arrHtml = arr ? arr.outerHTML : '<span class="arr">▼</span>';
        tds[4].innerHTML = barHtml + fmtN(g.cost||0) + arrHtml;
      }
      // 상세 행 (gd id="g_noconv-N")
      var gd = document.getElementById('g_noconv-'+idx);
      if(!gd) return;
      var inner = gd.querySelector('table.sdt tbody');
      if(!inner) return;
      var items = g.items||[];
      var rowsHtml = items.map(function(it, i){
        var nameCell = linkify(it.name||it.pid, it.url);
        return '<tr>' +
          '<td style="color:var(--muted);width:30px">'+ (i+1) +'</td>' +
          '<td style="font-size:11px;color:var(--muted)">'+ escapeHtml(it.campaign||'') +'</td>' +
          '<td style="font-size:11px">'+ escapeHtml(it.adgroup||'') +'</td>' +
          '<td class="bold">'+ nameCell +'</td>' +
          '<td class="r">'+ fmtN(it.cost||0) +'</td>' +
          '<td class="r">'+ fmtN(it.clk||0) +'</td>' +
          '</tr>';
      }).join('');
      inner.innerHTML = rowsHtml;
    });
    // 비전환 헤더 (총 X원이 비전환 소진)
    var headerEl = document.querySelector('h2 .badge');
    var noConvCost = D.no_conv_total || (D.report ? D.report.no_conv_cost : 0) || 0;
    var noConvPct = D.report ? D.report.no_conv_pct : 0;
    document.querySelectorAll('h2').forEach(function(h2){
      if(h2.textContent.indexOf('비전환 광고비') >= 0){
        var b = h2.querySelector('.badge');
        if(b) b.textContent = '광고비의 ' + (noConvPct||0).toFixed(1) + '%';
        var desc = h2.nextElementSibling;
        if(desc && desc.classList && desc.classList.contains('desc')){
          var bold = desc.querySelector('b');
          if(bold) bold.textContent = '총 ' + fmtN(noConvCost) + '원';
        }
      }
    });
  }
  function overlayHeader(){
    var gen = document.querySelectorAll('.gen');
    gen.forEach(function(el){
      el.textContent = '🕐 생성: ' + D.meta.generated_at + ' · 데이터 기준: ' + D.meta.date + ' (' + D.meta.weekday + ')';
    });
  }
  function overlayB(){
    var nb = D.naver_b||{}, total = nb.total||{}, conv = D.b_conv||{};
    var panel = document.getElementById('p-naver-b');
    if(!panel) return;
    var cards = panel.querySelectorAll('.kpi .card');
    if(cards[0]){ var v=cards[0].querySelector('.val'); if(v) v.textContent=fmtN(total.imp); }
    if(cards[1]){
      var v=cards[1].querySelector('.val'); if(v) v.textContent=fmtN(total.clk);
      var s=cards[1].querySelector('.sub'); if(s) s.textContent='CTR '+ratio2(total.clk,total.imp);
    }
    if(cards[2]){
      var v=cards[2].querySelector('.val'); if(v) v.innerHTML=fmtN(total.cost)+'<span class="unit">원</span>';
      var s=cards[2].querySelector('.sub'); if(s) s.textContent='CPC '+fmtN(roundCpc(total.cost,total.clk))+'원';
    }
    if(cards[3]){
      var v=cards[3].querySelector('.val'); if(v) v.innerHTML=fmtN(conv.v||0)+'<span class="unit">원</span>';
      var s=cards[3].querySelector('.sub'); if(s) s.textContent='전환 '+(conv.n||0)+'건';
    }
    if(cards[4]){
      var v=cards[4].querySelector('.val'); if(v) v.innerHTML=ratio1(conv.v||0,total.cost).replace('%','<span class="unit">%</span>');
      var s=cards[4].querySelector('.sub'); if(s) s.textContent='매출/광고비';
    }
    if(cards[5]){
      var v=cards[5].querySelector('.val'); if(v) v.innerHTML=(nb.share_pct||0).toFixed(1)+'<span class="unit">%</span>';
      var s=cards[5].querySelector('.sub'); if(s) s.textContent='전체 광고비 대비';
    }
    var camps = nb.campaigns||[];
    var ghs = panel.querySelectorAll('tr.gh[data-tgt^="b_tree_"]');
    ghs.forEach(function(row, idx){
      if(idx >= camps.length){ row.style.display='none'; var sib = row.nextElementSibling;
        while(sib && sib.classList && sib.classList.contains('gd')){ sib.style.display='none'; sib=sib.nextElementSibling; }
        return;
      }
      var c = camps[idx]; var tds = row.querySelectorAll('td');
      if(tds[1]) tds[1].textContent = c.name || c.cid || '';
      if(tds[2]) tds[2].textContent = (nb.active_per_camp && nb.active_per_camp[c.cid] ? nb.active_per_camp[c.cid]+'개 활성' : (tds[2].textContent.indexOf('활성')>=0 ? tds[2].textContent : '-'));
      if(tds[3]) tds[3].textContent = fmtN(c.imp);
      if(tds[4]) tds[4].textContent = fmtN(c.clk);
      if(tds[5]) tds[5].innerHTML = '<b>'+fmtN(c.cost)+'</b><span class="unit">원</span> <span class="ex">▼</span>';
    });
    var adgs = nb.adgroups||[];
    var adgsByCid = {};
    adgs.forEach(function(a){
      var cid = a.cid || '';
      if(!adgsByCid[cid]) adgsByCid[cid] = [];
      adgsByCid[cid].push(a);
    });
    camps.forEach(function(c, ci){
      var gdRow = panel.querySelector('tr.gd[id="b_tree_'+ci+'"]');
      if(!gdRow) return;
      var innerRows = gdRow.querySelectorAll('table tbody > tr');
      var campAdgs = adgsByCid[c.cid] || [];
      innerRows.forEach(function(row, idx){
        if(idx >= campAdgs.length){ row.style.display='none'; return; }
        var a = campAdgs[idx]; var tds = row.querySelectorAll(':scope > td');
        if(tds[1]) tds[1].textContent = a.name || '';
        if(tds[2]){
          var _hl = a.headline || '';
          var _url = a.url || '';
          if(_url && _hl) tds[2].innerHTML = '<a href="'+_url+'" target="_blank" style="color:inherit;border-bottom:1px dashed var(--muted);text-decoration:none">'+_hl+' ↗</a>';
          else if(_hl) tds[2].textContent = _hl;
          else tds[2].textContent = '';
        }
        if(tds[3]) tds[3].textContent = fmtN(a.imp);
        if(tds[4]) tds[4].textContent = fmtN(a.clk);
        if(tds[5]) tds[5].textContent = ratio2(a.clk, a.imp);
        if(tds[6]) tds[6].innerHTML = '<b>'+fmtN(a.cost)+'</b>';
      });
    });
    var sections = panel.querySelectorAll('h2');
    sections.forEach(function(h2){
      var t = h2.textContent || '';
      if(t.indexOf('광고그룹 TOP') >= 0){
        var table = h2.parentElement.querySelector('table.dt');
        if(table){
          var trs = table.querySelectorAll('tbody tr');
          var top15 = adgs.slice(0,15);
          trs.forEach(function(row, idx){
            if(idx >= top15.length){ row.style.display='none'; return; }
            var a = top15[idx]; var tds = row.querySelectorAll('td');
            if(tds[1]) tds[1].textContent = a.name || '';
            if(tds[2]) tds[2].textContent = a.campaign || '';
            if(tds[3]) tds[3].textContent = fmtN(a.imp);
            if(tds[4]) tds[4].textContent = fmtN(a.clk);
            if(tds[5]) tds[5].textContent = ratio2(a.clk, a.imp);
            if(tds[6]) tds[6].innerHTML = '<b>'+fmtN(a.cost)+'</b>';
          });
        }
      }
    });
  }
  function overlayG(){
    var g = D.google||{}, total = g.total||{}, dev = g.devices||{};
    var panel = document.getElementById('p-google');
    if(!panel) return;
    var cards = panel.querySelectorAll('.kpi .card');
    if(cards[0]){ var v=cards[0].querySelector('.val'); if(v) v.textContent=fmtN(total.imp); }
    if(cards[1]){
      var v=cards[1].querySelector('.val'); if(v) v.textContent=fmtN(total.clk);
      var s=cards[1].querySelector('.sub'); if(s) s.textContent='CTR '+ratio2(total.clk,total.imp);
    }
    if(cards[2]){
      var v=cards[2].querySelector('.val'); if(v) v.innerHTML=fmtN(total.cost)+'<span class="unit">원</span>';
      var s=cards[2].querySelector('.sub'); if(s) s.textContent='CPC '+fmtN(roundCpc(total.cost,total.clk))+'원';
    }
    if(cards[3]){
      var v=cards[3].querySelector('.val'); if(v) v.textContent=Number(total.conv||0).toFixed(0);
    }
    if(cards[4]){
      var v=cards[4].querySelector('.val'); if(v) v.innerHTML=fmtN(g.buy_v||0)+'<span class="unit">원</span>';
      var s=cards[4].querySelector('.sub'); if(s){ s.textContent=D.meta.date+' '+(g.buy_n||0)+'건'; if((g.buy_v||0)===0) s.style.color='#fbbf24';}
    }
    if(cards[5]){
      var v=cards[5].querySelector('.val'); if(v){ v.innerHTML=(g.roas||0).toFixed(1)+'<span class="unit">%</span>'; if((g.buy_v||0)===0) v.style.color='#fbbf24';}
      var s=cards[5].querySelector('.sub'); if(s) s.textContent=(g.buy_n||0)+'건 매출';
    }
    var trend = g.trend||[];
    var detailsAll = panel.querySelectorAll('details.aux');
    detailsAll.forEach(function(det){
      var sumText = det.querySelector('summary').textContent || '';
      if(sumText.indexOf('8일 추이') >= 0){
        var summary = det.querySelector('summary');
        if(summary){
          var firstD = trend.length ? trend[0].date : '';
          var lastD = trend.length ? trend[trend.length-1].date : D.meta.date;
          summary.innerHTML = '📈 8일 추이 (' + firstD + '~' + lastD + ')<span class="badge">진짜 매출 = "구매" 액션만</span>';
        }
        var tbody = det.querySelector('tbody');
        if(tbody && trend.length){
          var maxCost = Math.max.apply(null, trend.map(function(t){return t.cost||0;})) || 1;
          tbody.innerHTML = trend.map(function(t){
            var w = Math.round((t.cost||0)/maxCost*100);
            return '<tr><td style="padding:11px 14px;color:#fff;font-weight:600">' + t.date + '</td>' +
              '<td style="padding:11px 14px"><div style="background:linear-gradient(90deg,#a78bfa,#7c3aed);height:8px;width:'+w+'%;border-radius:3px"></div></td>' +
              '<td style="padding:11px 14px;text-align:right">' + fmtN(t.clk) + '</td>' +
              '<td style="padding:11px 14px;text-align:right;font-weight:600">' + fmtN(t.cost) + '</td>' +
              '<td style="padding:11px 14px;text-align:right">0</td></tr>';
          }).join('');
        }
      }
      if(sumText.indexOf('검색어') >= 0){
        var st = g.search_terms||[];
        var tbody = det.querySelector('tbody');
        if(tbody && st.length){
          tbody.innerHTML = st.map(function(t,i){
            var _adgCell = (t.url) ?
              '<a href="'+t.url+'" target="_blank" style="color:var(--sub);border-bottom:1px dashed var(--muted);text-decoration:none">'+(t.adgroup||'')+' ↗</a>' :
              (t.adgroup||'');
            return '<tr><td style="padding:9px 12px;color:var(--muted)">'+ (i+1) +'</td>' +
              '<td style="padding:9px 12px;color:#fff;font-weight:500">'+ (t.term||'') +'</td>' +
              '<td style="padding:9px 12px;font-size:12px">'+ _adgCell +'</td>' +
              '<td style="padding:9px 12px;text-align:right">'+ fmtN(t.clk) +'</td>' +
              '<td style="padding:9px 12px;text-align:right;font-weight:600">'+ fmtN(t.cost) +'</td>' +
              '<td style="padding:9px 12px;text-align:right">'+ Number(t.conv||0).toFixed(1) +'</td></tr>';
          }).join('');
        }
      }
      // === 메인 "실제 사용자 검색어" 표 (g_st_0~9) 동적 채우기 ===
    });

    // 메인 검색어 표 갱신
    var st = g.search_terms || [];
    for(var i=0;i<10;i++){
      var gh = document.querySelector('tr.gh[data-tgt="g_st_'+i+'"]');
      var gd = document.getElementById('g_st_'+i);
      if(!gh) continue;
      if(i >= st.length){
        gh.style.display='none';
        if(gd) gd.style.display='none';
        continue;
      }
      var t = st[i];
      var tds = gh.querySelectorAll('td');
      // 0:순위 1:검색어 2:매칭 3:노출 4:클릭 5:CTR 6:bar 7:광고비
      if(tds[1]) tds[1].textContent = t.term || '';
      if(tds[2]) tds[2].innerHTML = (t.match_label||'-') + ' <span style="color:var(--muted);font-size:10.5px;font-weight:400">('+(t.match_type||'')+')</span>';
      if(tds[3]) tds[3].textContent = fmtN(t.imp||0);
      if(tds[4]) tds[4].textContent = fmtN(t.clk||0);
      if(tds[5]) tds[5].textContent = ratio2(t.clk||0, t.imp||0);
      if(tds[7]){
        var arr = tds[7].querySelector('.arr');
        var arrHtml = arr ? arr.outerHTML : '<span class="arr">▼</span>';
        tds[7].innerHTML = fmtN(t.cost||0) + ' ' + arrHtml;
      }
      // 펼침 안 광고그룹·헤드라인 → 매핑 키워드 · 랜딩 URL
      if(gd){
        var tbody = gd.querySelector('tbody');
        if(tbody){
          var kw = t.url_kw || t.matched_kw || t.term || '';
          var urlCell = t.url ?
            '<a href="'+t.url+'" target="_blank" style="color:#7dd3fc;border-bottom:1px dashed var(--muted);text-decoration:none">'+t.url+' ↗</a>' :
            '<span style="color:var(--muted)">URL 없음</span>';
          tbody.innerHTML =
            '<tr><td style="padding:9px 14px;color:#fff;font-weight:500">'+ (t.adgroup||'') +'</td>' +
            '<td style="padding:9px 14px"><div style="color:#a5b4fc;margin-bottom:3px">매칭 키워드: <b>'+kw+'</b></div>' + urlCell + '</td></tr>';
        }
      }
    }

    detailsAll.forEach(function(det){
      var sumText = det.querySelector('summary').textContent || '';
      if(sumText.indexOf('디바이스') >= 0){
        var devLabel = {'MOBILE':'모바일','DESKTOP':'PC','TABLET':'태블릿'};
        var tbody = det.querySelector('tbody');
        if(tbody){
          var keys = Object.keys(dev);
          if(keys.length){
            tbody.innerHTML = keys.map(function(k){
              var d = dev[k];
              return '<tr><td style="padding:11px 14px;color:#fff;font-weight:600">'+ (devLabel[k]||k) +'</td>' +
                '<td style="padding:11px 14px;text-align:right">'+ fmtN(d.cost) +'</td>' +
                '<td style="padding:11px 14px;text-align:right">'+ fmtN(d.clk) +'</td></tr>';
            }).join('');
          }
        }
      }
    });
  }

  // === PATCH: direct/indirect 컬럼 hide (코드 d_buy_v 항상 0 — 영구 거짓 표시) ===
  function hideDirectIndirectCols(){
    document.querySelectorAll('table').forEach(function(t){
      var ths = t.querySelectorAll('thead th');
      var hideIdx = [];
      ths.forEach(function(th, idx){
        var tx = (th.textContent||'').trim();
        if (tx === '직접' || tx === '간접' || tx === '직접매출' || tx === '간접매출') {
          hideIdx.push(idx);
          th.style.display = 'none';
        }
      });
      if (hideIdx.length) {
        t.querySelectorAll('tbody tr').forEach(function(tr){
          var tds = tr.querySelectorAll(':scope > td');
          hideIdx.forEach(function(i){ if (tds[i]) tds[i].style.display = 'none'; });
        });
      }
    });
    // desc 안 "●직접/●간접" 설명 문구 숨김
    document.querySelectorAll('.desc').forEach(function(d){
      var html = d.innerHTML;
      if (html.indexOf('●직접') >= 0 || html.indexOf('●간접') >= 0) {
        d.innerHTML = html.replace(/<span[^>]*>●직접[^<]*<\/span>[^<]*,?\s*<span[^>]*>●간접[^<]*<\/span>[^.]*\.?/g, '');
      }
    });
  }

  // === PATCH: 정적 카드 값을 placeholder로 (JS 실패 시 잘못된 값 노출 방지) ===
  // JS overlay가 정상 실행되면 즉시 D 값으로 덮여서 영향 없음. 실패 시 '-' 표시되어 사고 인지 가능.
  // 단, overlay 실행 전(이 함수 호출 직전)에는 정적값이 잠깐 보일 수 있으므로 overlay 다음에 호출.
  // 이 함수는 정적값 detection 후 '-' 치환 (overlay가 이미 채운 값은 보존)
  function placeholderizeStaticCards(){
    // overlay 이후 호출이라 이미 정상 값이면 그대로 둠. 이 함수는 no-op.
    // 정적값 사고 방지의 핵심은 _init_overlays의 try/catch + readyState 체크.
  }

  // === 신규: 클릭있는데 구매 전 (2026-05-18) ===
  function overlayClickNoBuy(){
    var list = D.click_no_buy || [];
    var total = D.click_no_buy_total || {count:0, clk_sum:0, cost_sum:0};
    var badge = document.getElementById('cnb_badge');
    if (badge) badge.textContent = '총 ' + (total.count||0) + '개 / 클릭 ' + fmtN(total.clk_sum||0) + ' / 광고비 ' + fmtN(total.cost_sum||0) + '원';
    var tb = document.getElementById('cnb_tbody');
    if (!tb) return;
    if (!list.length) {
      tb.innerHTML = '<tr><td colspan="7" style="padding:20px;text-align:center;color:var(--muted)">데이터 없음</td></tr>';
      return;
    }
    var maxClk = Math.max.apply(null, list.map(function(c){return c.clk||0;})) || 1;
    var html = '';
    list.forEach(function(c, i){
      var ctr = c.imp>0 ? (c.clk/c.imp*100).toFixed(2)+'%' : '-';
      var w = Math.max(2, (c.clk||0)/maxClk*80);
      var nameCell = c.url ?
        '<a href="'+escapeHtml(c.url)+'" target="_blank" style="color:#fff;border-bottom:1px dotted rgba(255,255,255,0.3);text-decoration:none">'+escapeHtml(c.name||'-')+' ↗</a>' :
        escapeHtml(c.name||'-');
      var thumbCell = c.thumb ?
        '<img src="'+escapeHtml(c.thumb)+'" style="width:38px;height:38px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:8px" loading="lazy">' : '';
      html += '<tr class="gh" data-tgt="cnb-'+i+'">' +
        '<td><span class="rank '+(i<3?'top1':'')+'">'+(i+1)+'</span></td>' +
        '<td class="bold">'+thumbCell+nameCell+'</td>' +
        '<td class="r">'+fmtN(c.imp||0)+'</td>' +
        '<td class="r bold"><span class="bar" style="width:'+w+'px;background:#3b82f6"></span>'+fmtN(c.clk||0)+'</td>' +
        '<td class="r">'+ctr+'</td>' +
        '<td class="r">'+(c.camps?c.camps.length:0)+'</td>' +
        '<td class="r bold">'+fmtN(c.cost||0)+'</td>' +
        '</tr>';
      // 펼침 — 캠페인/광고그룹 분산
      var campsHtml = (c.camps||[]).map(function(x){return escapeHtml(x);}).join('<br>') || '-';
      var grpsHtml = (c.grps||[]).map(function(x){return escapeHtml(x);}).join('<br>') || '-';
      html += '<tr class="gd" id="cnb-'+i+'" style="display:none"><td colspan="7" style="background:#080b14;padding:14px">' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;font-size:11.5px">' +
        '<div><div style="color:var(--muted);margin-bottom:6px">📂 분산된 캠페인 ('+(c.camps?c.camps.length:0)+')</div><div style="color:#fff;line-height:1.6">'+campsHtml+'</div></div>' +
        '<div><div style="color:var(--muted);margin-bottom:6px">🎯 광고그룹 ('+(c.grps?c.grps.length:0)+')</div><div style="color:#fff;line-height:1.6">'+grpsHtml+'</div></div>' +
        '</div></td></tr>';
    });
    tb.innerHTML = html;
    // 펼침 토글 바인딩
    tb.querySelectorAll('tr.gh').forEach(function(row){
      row.style.cursor = 'pointer';
      row.addEventListener('click', function(){
        var id = row.getAttribute('data-tgt');
        var gd = document.getElementById(id);
        if (gd) gd.style.display = (gd.style.display==='none' ? 'table-row' : 'none');
      });
    });
  }

  // === PATCH: 슬롯 부족 시 동적 확장 (B 캠페인 7개 > 슬롯 4개, 비전환 27개 > 슬롯 12개) ===
  function expandSlotsIfNeeded(){
    // 1) B 캠페인 트리 슬롯 확장
    var bPanel = document.getElementById('p-naver-b');
    if (bPanel && D.naver_b && D.naver_b.campaigns) {
      var camps = D.naver_b.campaigns;
      var firstGh = bPanel.querySelector('tr.gh[data-tgt="b_tree_0"]');
      var firstGd = bPanel.querySelector('tr.gd[id="b_tree_0"]');
      if (firstGh && firstGd) {
        var existing = bPanel.querySelectorAll('tr.gh[data-tgt^="b_tree_"]').length;
        for (var i = existing; i < camps.length; i++) {
          var newGh = firstGh.cloneNode(true);
          newGh.setAttribute('data-tgt', 'b_tree_'+i);
          firstGd.parentNode.insertBefore(newGh, null);
          var newGd = firstGd.cloneNode(true);
          newGd.id = 'b_tree_'+i;
          newGd.style.display = 'none';
          firstGd.parentNode.appendChild(newGd);
        }
        // 추가 후 overlayB 재호출해서 새 슬롯 채움
        try { overlayB(); } catch(e){ console.error('overlayB rerun',e); }
      }
    }
    // 2) 비전환 그룹 슬롯 확장
    if (D.no_conv_groups) {
      var groups = D.no_conv_groups;
      var firstNcGh = document.querySelector('tr.gh[data-tgt="g_noconv-0"]');
      var firstNcGd = document.getElementById('g_noconv-0');
      if (firstNcGh && firstNcGd) {
        var existing = document.querySelectorAll('tr.gh[data-tgt^="g_noconv-"]').length;
        for (var i = existing; i < groups.length; i++) {
          var newGh = firstNcGh.cloneNode(true);
          newGh.setAttribute('data-tgt', 'g_noconv-'+i);
          firstNcGd.parentNode.appendChild(newGh);
          var newGd = firstNcGd.cloneNode(true);
          newGd.id = 'g_noconv-'+i;
          newGd.style.display = 'none';
          firstNcGd.parentNode.appendChild(newGd);
        }
        // 추가 후 overlayNoConv 재호출
        try { overlayNoConv(); } catch(e){ console.error('overlayNoConv rerun',e); }
      }
    }
  }

})();
</script>
"""

# PATCH (2026-05-18): 카드 .val 정적값을 placeholder로 치환 (JS overlay 실패 시 잘못된 값 노출 방지)
import re as _re_ph
def _placeholderize(html):
    # <div class="card ..."><div class="label">...</div><div class="val">VALUE<span class="unit">...</span></div>...
    # VALUE를 '-'로 치환. 단위(span)는 보존.
    pattern = _re_ph.compile(
        r'(<div class="card[^"]*"><div class="label">[^<]+</div><div class="val">)[^<]+(<span[^>]*>[^<]+</span>)?(</div>)',
        _re_ph.DOTALL
    )
    return pattern.sub(lambda m: m.group(1) + '-' + (m.group(2) or '') + m.group(3), html)
new_src = _placeholderize(new_src)

# === 메인 패널 h2 num span 순차 재번호 (2번 제거 + 신규 섹션 + 이모지 통일) ===
# 차장님 지시: "번호도 잘 맞추고"
import re as _re_num
def _renumber_main(html):
    # p-naver-b 패널 시작 전까지를 메인 패널로 간주
    cutoff = html.find('id="p-naver-b"')
    if cutoff < 0:
        cutoff = html.find('id="p-google"')
    if cutoff < 0:
        cutoff = len(html)
    main_html = html[:cutoff]
    rest = html[cutoff:]
    counter = [0]
    def _repl(m):
        counter[0] += 1
        # num span 내용을 순차 번호로 교체. 단 style은 보존
        return _re_num.sub(r'>[^<]+<', f'>{counter[0]}<', m.group(), count=1)
    new_main = _re_num.sub(r'<span class="num"[^>]*>[^<]+</span>', _repl, main_html)
    return new_main + rest
# === 신규: TOP 20 click_no_buy 상품 썸네일 fetch (GitHub Actions 환경에서 시도) ===
def _fetch_thumb(url):
    if not url: return ""
    # 모바일 URL로 변환 (smartstore → m.smartstore). desktop URL은 봇 차단됨
    mobile = url.replace('://smartstore.', '://m.smartstore.')
    try:
        req = urllib.request.Request(mobile, headers={
            "User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language":"ko-KR,ko;q=0.9,en;q=0.8",
        })
        html = urllib.request.urlopen(req, context=ctx, timeout=8).read().decode('utf-8','ignore')
        import re as _re_th
        m = _re_th.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if not m:
            m = _re_th.search(r'<meta[^>]*content="([^"]+)"[^>]*property="og:image"', html)
        if not m:
            m = _re_th.search(r'(https://shop-phinf\.pstatic\.net/[^\s"\\)]+\.(?:jpg|png|jpeg|webp)[^\s"\\)]*)', html)
        return m.group(1) if m else ""
    except Exception:
        return ""
print("  click_no_buy 썸네일 fetch 시작...", file=sys.stderr)
import time as _time
_thumb_ok = 0
for _c in D.get("click_no_buy", []):
    _c["thumb"] = _fetch_thumb(_c.get("url",""))
    if _c["thumb"]: _thumb_ok += 1
    _time.sleep(0.3)  # rate limit 회피
print(f"  썸네일: {_thumb_ok}/{len(D.get('click_no_buy',[]))} 성공", file=sys.stderr)

# D 객체 재직렬화 후 src에 다시 주입 (썸네일 반영)
_s_d = new_src.find("const D = ")
if _s_d > 0:
    _i_d = _s_d + 10; _depth=0; _end=-1; _in_str=False; _esc=False
    while _i_d < len(new_src):
        _c2 = new_src[_i_d]
        if _in_str:
            if _esc: _esc=False
            elif _c2=='\\': _esc=True
            elif _c2=='"': _in_str=False
        else:
            if _c2=='"': _in_str=True
            elif _c2=='{': _depth+=1
            elif _c2=='}':
                _depth-=1
                if _depth==0: _end=_i_d+1; break
        _i_d += 1
    if _end > 0:
        new_src = new_src[:_s_d+10] + json.dumps(D, ensure_ascii=False) + new_src[_end:]

# === 2번 "클릭 — 상품군 전체" 섹션 제거 (1번 광고비 소진과 같은 데이터 다른 정렬 — 중복) ===
# 2026-05-18 차장 지시: "어차피 필터로 소팅되니까 하나만"
import re as _re_rm
_pat_click = _re_rm.compile(
    r'<div class="section click">\s*<h2>[^<]*<span class="num">2</span>클릭 — 상품군 전체.*?<tbody id="g_click"></tbody>\s*</table>\s*</div>',
    _re_rm.DOTALL
)
new_src = _pat_click.sub('', new_src, count=1)

# === 신규 섹션: "클릭있고 구매 전" 상품 (2026-05-18 차장 지시) ===
# 위치: 5번 "비전환 광고비" 섹션 직전에 삽입
_new_section = """
<div class="section" id="sec-click-no-buy">
  <h2><span class="num" style="background:#3b82f6">💡</span>클릭있는데 구매 전 — 잠재 후보<span class="badge" id="cnb_badge">-</span></h2>
  <div class="desc">광고 클릭은 발생했지만 아직 구매로 이어지지 않은 상품. 상세페이지·가격·CS 통화 점검 / 입찰가 조정 검토. 상품행 클릭 시 캠페인·광고그룹 분산 펼침.</div>
  <table class="dt" style="width:100%;table-layout:fixed">
    <colgroup><col style="width:50px"><col><col style="width:70px"><col style="width:80px"><col style="width:90px"><col style="width:70px"><col style="width:100px"></colgroup>
    <thead><tr>
      <th>#</th><th>상품명</th><th class="r">노출</th><th class="r">클릭</th><th class="r">CTR</th><th class="r">캠페인수</th><th class="r">광고비 (원)</th>
    </tr></thead>
    <tbody id="cnb_tbody"></tbody>
  </table>
</div>
"""
# 비전환 광고비 섹션 직전(h2 안 '비전환 광고비' 텍스트)에 삽입
import re as _re_cnb
_pat = _re_cnb.compile(r'(<div class="section"[^>]*>\s*<h2[^>]*><span class="num"[^>]*>⚠</span>비전환)', _re_cnb.DOTALL)
new_src = _pat.sub(_new_section + r'\1', new_src, count=1)

# === 메인 패널 num span 순차 재번호 (모든 처리 끝난 후 마지막에) ===
new_src = _renumber_main(new_src)

new_src = new_src.replace("</body>", overlay_js + "\n</body>", 1)

OUT = os.path.join(WORKSPACE, f"네이버광고_1차보고대시보드_{TARGET}.html")
open(OUT,"w",encoding="utf-8").write(new_src)
print(f"[saved] {OUT} ({len(new_src):,}chars)", file=sys.stderr)

# === GitHub Pages 업로드 (매일 09:00 같은 URL 유지) === #
GH_PAT = os.environ.get("GITHUB_PAT","")
GH_OWNER = os.environ.get("GITHUB_OWNER","")
GH_REPO = os.environ.get("GITHUB_REPO","")
if GH_PAT and GH_OWNER and GH_REPO:
    def gh_put(path, content_bytes, msg):
        api = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
        # 기존 sha 확인
        sha = None
        try:
            req = urllib.request.Request(api, headers={"Authorization":f"Bearer {GH_PAT}","Accept":"application/vnd.github+json"})
            sha = json.loads(urllib.request.urlopen(req,context=ctx,timeout=15).read()).get("sha")
        except: pass
        body = {"message": msg, "content": base64.b64encode(content_bytes).decode()}
        if sha: body["sha"] = sha
        try:
            req = urllib.request.Request(api, data=json.dumps(body).encode(), method="PUT",
                headers={"Authorization":f"Bearer {GH_PAT}","Accept":"application/vnd.github+json","Content-Type":"application/json"})
            urllib.request.urlopen(req,context=ctx,timeout=20).read()
            return True
        except Exception as e:
            print(f"  GH push err {path}: {e}", file=sys.stderr); return False

    content = new_src.encode("utf-8")
    msg = f"ceo-report {TARGET} ({WEEKDAY})"
    ok1 = gh_put(f"ceo-report/latest.html", content, msg)
    ok2 = gh_put(f"ceo-report/{TARGET}.html", content, msg)
    if ok1 and ok2:
        print(f"  [GH push] latest.html + {TARGET}.html → https://{GH_OWNER}.github.io/{GH_REPO}/ceo-report/latest.html", file=sys.stderr)
else:
    print("  [GH push] 환경변수 미설정 — 스킵", file=sys.stderr)

print(f"\n=== {TARGET} ({WEEKDAY}) 통합 ===")
print(f"A: 광고비 {a_total['cost']:,}원 매출 {a_buy_total['v']:,}원 ROAS {a_roas}%")
print(f"B: 광고비 {b_total['cost']:,}원 매출 {b_conv['v']:,}원 ROAS {b_roas}%")
print(f"G: 광고비 {g_total['cost']:,}원 매출 {g_buy['v']:,}원 ROAS {g_roas}%")
print(f"통합: 광고비 {combined['cost']:,}원 매출 {combined['buy_v']:,}원 ROAS {combined['roas']}%")
print(f"비전환: {no_conv_total:,}원 ({no_conv_pct}%, {len(no_conv_groups)}그룹)")
print(f"파일: {OUT}")
