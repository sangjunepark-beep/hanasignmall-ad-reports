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
try:
    rows01 = gviz_csv(1416410435)
    rows02 = gviz_csv(1885328367)
    rows01_t = [r for r in rows01[1:] if r and r[0]==TARGET]
    rows02_t = [r for r in rows02[1:] if r and r[0]==TARGET]
    print(f"  시트 01:{len(rows01_t)} 02:{len(rows02_t)}", file=sys.stderr)
    seen_keys = set()
    for r in rows01_t:
        while len(r)<11: r.append("")
        k = (r[2], r[3], r[4])
        if k in seen_keys: continue
        seen_keys.add(k)
        pid = r[4]
        m = mp.get(pid,{})
        all_rows.append({"campaign":r[2],"adgroup":r[3],"pid":pid,"imp":to_int(r[5]),"clk":to_int(r[6]),
                         "cost":to_int(r[8]),"name":(r[10] or m.get("name","")).strip(),"url":m.get("url","")})
    seen_buy = set()
    for r in rows02_t:
        while len(r)<10: r.append("")
        if r[1] in seen_buy: continue
        seen_buy.add(r[1])
        buy_map[r[1]] = {"buy_n":to_int(r[2]),"buy_v":to_int(r[3]),"d_buy_n":to_int(r[4]),"d_buy_v":to_int(r[5]),
                         "i_buy_n":to_int(r[6]),"i_buy_v":to_int(r[7]),"cart_n":to_int(r[8]),"cart_v":to_int(r[9])}
except Exception as e:
    print(f"  시트 err: {e}", file=sys.stderr)

if not all_rows:
    print("  [A API fallback]", file=sys.stderr)
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

a_total = {"imp":sum(r["imp"] for r in all_rows),"clk":sum(r["clk"] for r in all_rows),
           "cost":sum(r["cost"] for r in all_rows),"count":len(all_rows)}
camp_agg = defaultdict(lambda:{"cost":0,"clk":0,"imp":0})
for r in all_rows:
    c=camp_agg[r["campaign"]]; c["cost"]+=r["cost"]; c["clk"]+=r["clk"]; c["imp"]+=r["imp"]
a_campaigns = sorted([{"name":k or "(미상)",**v} for k,v in camp_agg.items()], key=lambda x:-x["cost"])
top_cost = sorted(all_rows, key=lambda x:-x["cost"])[:20]
top_click = sorted(all_rows, key=lambda x:-x["clk"])[:20]

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
no_conv_groups = sorted([{"name":k,"cost":v["cost"],"clk":v["clk"],"imp":v["imp"],"count":v["count"],"items":v["items"][:10]}
                         for k,v in grp.items() if v["cost"]>0 and v["rev"]==0], key=lambda x:-x["cost"])
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
    rsp = gq(f"SELECT search_term_view.search_term,ad_group.name,metrics.clicks,metrics.cost_micros,metrics.conversions FROM search_term_view WHERE segments.date='{TARGET}' ORDER BY metrics.cost_micros DESC LIMIT 10")
    for ch in rsp or []:
        for row in ch.get("results",[]):
            m=row["metrics"]
            g_search_terms.append({"term":row["searchTermView"]["searchTerm"],"adgroup":row["adGroup"]["name"],
                                    "clk":int(m.get("clicks","0")),"cost":int(m.get("costMicros","0"))//1000000,
                                    "conv":float(m.get("conversions",0))})
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
    "naver_b":{"total":b_total,"campaigns":b_camps,"adgroups":b_adgs,
               "active_per_camp":dict(b_camp_active),
               "ctr":b_ctr,"cpc":b_cpc,"roas":b_roas,"share_pct":b_share},
    "b_conv":b_conv,
    "google":{"total":g_total,"buy_v":g_buy["v"],"buy_n":g_buy["n"],
              "campaigns":g_camps,"devices":g_devices,
              "search_terms":g_search_terms,"trend":g_trend,
              "ctr":g_ctr,"cpc":g_cpc,"roas":g_roas},
    "device_a":{"M":{"imp":0,"clk":0,"cost":0},"P":{"imp":0,"clk":0,"cost":0}},
    "hour_a":{f"{h:02d}":{"imp":0,"clk":0,"cost":0} for h in range(24)},
    "combined":combined,
}


# === HTML 빌드 === #
print("[4] HTML 빌드", file=sys.stderr)
TEMPLATE = os.path.join(WORKSPACE, "네이버광고_1차보고대시보드_2026-04-27.html")
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
  document.addEventListener('DOMContentLoaded', function(){
    overlayHeader(); overlayNoConv(); overlayB(); overlayG();
  });
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
            return '<tr><td style="padding:9px 12px;color:var(--muted)">'+ (i+1) +'</td>' +
              '<td style="padding:9px 12px;color:#fff;font-weight:500">'+ (t.term||'') +'</td>' +
              '<td style="padding:9px 12px;color:var(--sub);font-size:12px">'+ (t.adgroup||'') +'</td>' +
              '<td style="padding:9px 12px;text-align:right">'+ fmtN(t.clk) +'</td>' +
              '<td style="padding:9px 12px;text-align:right;font-weight:600">'+ fmtN(t.cost) +'</td>' +
              '<td style="padding:9px 12px;text-align:right">'+ Number(t.conv||0).toFixed(1) +'</td></tr>';
          }).join('');
        }
      }
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
})();
</script>
"""

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
print(f"통합: 광고비 {combined['cost']:,}원 매출 {combined['buy_v']:,}원 ROAS {combined['roas']}%")
print(f"비전환: {no_conv_total:,}원 ({no_conv_pct}%, {len(no_conv_groups)}그룹)")
print(f"파일: {OUT}")
                                                                                                           