# 네이버 검색광고 캠페인 추적 URL 설정 도구 (GitHub Actions에서 실행)
#  MODE=list  : 캠페인별 추적 관련 필드 현황 출력 (읽기 전용)
#  MODE=apply : NEW_MODE 값으로 trackingMode 일괄 변경 (TRACKING_DISABLED 캠페인만 대상)
import os, sys, json, time, hmac, base64, hashlib, urllib.request

N_BASE = "https://api.searchad.naver.com"
ACCTS = [
    ("A(쇼핑검색)", os.environ["A_KEY"], os.environ["A_SEC"], "1728536"),
    ("B(파워링크)", os.environ["B_KEY"], os.environ["B_SEC"], "1558945"),
]
MODE = os.environ.get("MODE", "list")
NEW_MODE = os.environ.get("NEW_MODE", "")

def n_sign(secret, m, p):
    ts = str(int(time.time() * 1000))
    return ts, base64.b64encode(hmac.new(secret.encode(), f"{ts}.{m}.{p}".encode(), hashlib.sha256).digest()).decode()

def n_req(key, secret, cid, m, p, body=None):
    ts, sig = n_sign(secret, m, p.split("?")[0])
    H = {"X-Timestamp": ts, "X-API-KEY": key, "X-Customer": cid, "X-Signature": sig, "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(N_BASE + p, data=data, method=m, headers=H), timeout=20).read())
    except urllib.error.HTTPError as e:
        print(f"  ERR {m} {p}: HTTP {e.code} {e.read().decode('utf-8','replace')[:300]}")
        return None
    except Exception as e:
        print(f"  ERR {m} {p}: {e}")
        return None

for label, key, sec, cid in ACCTS:
    print(f"\n===== {label} (customer {cid}) =====")
    camps = n_req(key, sec, cid, "GET", "/ncc/campaigns")
    if not isinstance(camps, list):
        print("  캠페인 조회 실패"); continue
    for c in camps:
        track = {k: v for k, v in c.items() if "rack" in k}  # tracking 관련 필드만
        print(f"  [{c.get('campaignTp')}] {c.get('name')} | id={c.get('nccCampaignId')} | status={c.get('status')} | {json.dumps(track, ensure_ascii=False)}")
        if MODE == "apply" and NEW_MODE:
            cur = c.get("trackingMode", "")
            if cur == NEW_MODE:
                print("      → 이미 설정됨, 건너뜀"); continue
            if cur not in ("", None, "TRACKING_DISABLED"):
                print(f"      → 현재 {cur} (자동변경 대상 아님, 건너뜀)"); continue
            body = dict(c)
            body["trackingMode"] = NEW_MODE
            r = n_req(key, sec, cid, "PUT", f"/ncc/campaigns/{c['nccCampaignId']}", body)
            print("      → 변경", "성공: " + str(r.get("trackingMode")) if isinstance(r, dict) else "실패")
print("\n완료 (MODE=%s)" % MODE)
