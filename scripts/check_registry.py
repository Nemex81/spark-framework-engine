import urllib.request, urllib.error, json
url = 'https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json'
out='scripts/check_registry.out'
try:
    req = urllib.request.Request(url, headers={"User-Agent":"check"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read(1024).decode('utf-8', errors='replace')
    data = {'reachable': True, 'sample': raw[:200]}
except Exception as e:
    data = {'reachable': False, 'error': str(e)}
open(out,'w',encoding='utf-8').write(json.dumps(data, ensure_ascii=False))
print('wrote', out)
