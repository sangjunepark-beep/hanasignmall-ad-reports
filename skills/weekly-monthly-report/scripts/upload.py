import os, json, base64, urllib.request, urllib.error, sys

token = os.environ['GITHUB_PAT']
owner = os.environ['GITHUB_OWNER']
repo = os.environ['GITHUB_REPO']

with open('/tmp/dark_report.html', 'rb') as f:
    content_b64 = base64.b64encode(f.read()).decode('ascii')

def put_file(target_path, msg):
    # 기존 SHA
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{target_path}'
    req = urllib.request.Request(url, headers={'Authorization': f'token {token}'})
    sha = None
    try:
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read())['sha']
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    
    body = {'message': msg, 'content': content_b64, 'branch': 'main'}
    if sha: body['sha'] = sha
    
    data = json.dumps(body).encode()
    req2 = urllib.request.Request(url, data=data, method='PUT',
        headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'})
    with urllib.request.urlopen(req2) as r:
        result = json.loads(r.read())
    return result.get('commit', {}).get('sha', '')[:12]

for target in ['weekly-product/2026-05-27.html', 'weekly-product/latest.html']:
    sha = put_file(target, f'feat(weekly-product): 다크모드 주월간 상품지표 ({target})')
    print(f'OK {target}: {sha}')
