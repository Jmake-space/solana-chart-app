import json, math, urllib.request, datetime
def get(url):
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
# spot index
idx=get("https://www.okx.com/api/v5/market/index-tickers?instId=SOL-USD")
print("index:", idx['data'])
S=float(idx['data'][0]['idxPx'])
tick=get("https://www.okx.com/api/v5/market/tickers?instType=OPTION&uly=SOL-USD")
inst=get("https://www.okx.com/api/v5/public/instruments?instType=OPTION&uly=SOL-USD")
exp={x['instId']: int(x['expTime'])/1000 for x in inst['data']}
stk={x['instId']: float(x['stk']) for x in inst['data']}
typ={x['instId']: x['optType'] for x in inst['data']}
now=datetime.datetime.now(datetime.timezone.utc).timestamp()
def N(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def bs(S,K,T,sigma,cp):
    if T<=0 or sigma<=0: return 0
    d1=(math.log(S/K)+0.5*sigma*sigma*T)/(sigma*math.sqrt(T)); d2=d1-sigma*math.sqrt(T)
    return S*N(d1)-K*N(d2) if cp=='C' else K*N(-d2)-S*N(-d1)
def iv(S,K,T,px,cp):
    lo,hi=0.01,5.0
    if bs(S,K,T,hi,cp)<px: return None
    for _ in range(80):
        mid=(lo+hi)/2
        if bs(S,K,T,mid,cp)<px: lo=mid
        else: hi=mid
    return (lo+hi)/2
rows=[]
for t in tick['data']:
    iid=t['instId']
    if not t.get('bidPx') or not t.get('askPx'): continue
    mid=(float(t['bidPx'])+float(t['askPx']))/2
    T=(exp[iid]-now)/86400
    if T<=0: continue
    v=iv(S,stk[iid],T/365,mid,typ[iid])
    if v: rows.append((iid,typ[iid],stk[iid],round(T,2),round(mid,3),round(v*100,1)))
rows.sort(key=lambda r:(r[3],abs(r[2]-S)))
for r in rows: print(r)
print("spot",S,"now",datetime.datetime.now(datetime.timezone.utc).isoformat())
json.dump({"spot":S,"ts_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"rows":rows}, open('/tmp/iv_out.json','w'), indent=1)
