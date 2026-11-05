import json,re,difflib,subprocess
R='/tmp/s_PhenixRebirth/assets/music/lyrics/'
norm=lambda w:re.sub(r"[^a-z0-9]","",w.lower())
def glob(lines,tw):
    lw=[];own=[];tws=[w for w,_ in tw]
    for i,l in enumerate(lines):
        for w in l['text'].split():
            if norm(w): lw.append(norm(w)); own.append(i)
    sm=difflib.SequenceMatcher(None,lw,tws,autojunk=False); c={}
    for a,b,n in sm.get_matching_blocks():
        for k in range(n):
            i=own[a+k]; pos=sum(1 for jj in range(a+k) if own[jj]==i)
            if i not in c: c[i]=max(0,tw[b+k][1]-0.35*pos)
    return c
def win(lines,tw):
    c={};p=0;tws=[w for w,_ in tw]
    for i,l in enumerate(lines):
        L=[norm(w) for w in l['text'].split() if norm(w)]
        if not L: continue
        best=(0,None)
        for st in range(p,min(len(tws),p+70)):
            r=difflib.SequenceMatcher(None,L,tws[st:st+len(L)],autojunk=False).ratio()
            if r>best[0]+0.08: best=(r,st)
        if best[0]>=0.55: c[i]=tw[best[1]][1]; p=best[1]+max(1,len(L)-1)
    return c
def ver(l,t,tw):
    L=set(norm(w) for w in l['text'].split() if norm(w))
    near=[w for w,s in tw if t-0.5<=s<t+3.5]
    return len(L&set(near))/max(1,min(len(L),4))
rep={}
for key in "lyra_eternal_dawn lyra_what_we_lost lyra_no_mercy_left lyra_oldest_fear lyra_when_we_looked_up lyra_when_we_looked_up_unplugged".split():
    d=json.loads(subprocess.run(['git','-C','/tmp/s_PhenixRebirth','show',f'HEAD:assets/music/lyrics/{key}.json'],capture_output=True,text=True).stdout)
    tw=json.load(open(f'tw_{key}.json')); lines=d['lines']
    A=win(lines,tw); B=glob(lines,tw)
    sung=[i for i,l in enumerate(lines) if l['text']]
    T={};last=-1
    for i in sung:
        cs=[t for t in (A.get(i),B.get(i)) if t is not None and t>last+0.8 and ver(lines[i],t,tw)>=0.5]
        # avoid jumping way ahead: pick the earliest verified
        if cs: T[i]=min(cs); last=T[i]
    ks=sorted(T); direct=len(ks)
    for i in sung:
        if i in T: continue
        lo=max([k for k in ks if k<i],default=None); hi=min([k for k in ks if k>i],default=None)
        si=sung.index
        if lo is not None and hi is not None: T[i]=T[lo]+(T[hi]-T[lo])*(si(i)-si(lo))/(si(hi)-si(lo))
        elif lo is not None: T[i]=T[lo]+4*(si(i)-si(lo))
        else: T[i]=max(0,T[hi]-4*(si(hi)-si(i)))
    out=[]
    for i,l in enumerate(lines):
        out.append({'t':round(T[i],2)}|{k:v for k,v in l.items() if k!='t'} if l['text'] else {'text':''})
    d['lines']=out
    json.dump(d,open(R+key+'.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    v=sum(ver(lines[i],T[i],tw)>=0.5 for i in sung)
    rep[key]=(direct,len(sung),v)
    print(key,'direct',direct,'/',len(sung),'verified',v)
    for i in sung[::7]: print(f"   {T[i]:6.1f} {lines[i]['text'][:40]:40} || {' '.join(w for w,s in tw if T[i]-0.3<=s<T[i]+3)[:50]}")
