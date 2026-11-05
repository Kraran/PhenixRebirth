import json,re,sys,difflib,os
from faster_whisper import WhisperModel
R='/tmp/s_PhenixRebirth/assets/music/lyrics/'
SONGS={'lyra_eternal_dawn':'lyra_1_eternal_dawn','lyra_what_we_lost':'lyra_2_what_we_lost','lyra_no_mercy_left':'lyra_3_no_mercy_left',
 'lyra_oldest_fear':'Lyra-Voss-Oldest-Fear','lyra_when_we_looked_up':'concertmars','lyra_when_we_looked_up_unplugged':'Lyra-Voss-When-We-Looked-Up-Unplugged'}
norm=lambda w:re.sub(r"[^a-z0-9]","",w.lower())
m=WhisperModel(os.environ.get('M','small.en'),device='cpu',compute_type='int8',cpu_threads=8)
rep={}
for key in sys.argv[1:]:
    d=json.load(open(R+key+'.json',encoding='utf-8'))
    import subprocess,numpy as np
    au=np.frombuffer(subprocess.run(['ffmpeg','-loglevel','quiet','-i',f'sep/htdemucs/{SONGS[key]}/vocals.wav','-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout,np.float32)
    segs,_=([],0) if os.path.exists(f'tw_{key}.json') else m.transcribe(au,word_timestamps=True,vad_filter=False,initial_prompt=' '.join(l['text'] for l in d['lines'] if l['text'])[:800],language='en',
                        condition_on_previous_text=False)
    cf=f'tw_{key}.json'
    if os.path.exists(cf): tw=json.load(open(cf))
    else:
        tw=[(norm(w.word),w.start) for s in segs for w in s.words if norm(w.word)]; json.dump(tw,open(cf,'w'))
    T0={};p=0;tws=[w for w,_ in tw];hits={}
    for i,l in enumerate(d['lines']):
        L=[norm(w) for w in l['text'].split() if norm(w)]
        if not L: continue
        best=(0,None)
        for st in range(p,min(len(tws),p+70)):
            r=difflib.SequenceMatcher(None,L,tws[st:st+len(L)],autojunk=False).ratio()
            if r>best[0]+0.08: best=(r,st)
        hits[i]=best[0]
        if best[0]>=0.55:
            st=best[1]
            # first word that actually matches L[0..1]
            T0[i]=tw[st][1]; p=st+max(1,len(L)-1)
    first=T0
    sung=[i for i,l in enumerate(d['lines']) if l['text']]
    good=[i for i in sung if i in first]
    # enforce monotonic: drop outliers
    T={};last=-1
    for i in good:
        if first[i]>last+0.8: T[i]=first[i]; last=first[i]
    ks=sorted(T)
    for i in sung:
        if i in T: continue
        lo=max([k for k in ks if k<i],default=None); hi=min([k for k in ks if k>i],default=None)
        if lo is not None and hi is not None: T[i]=T[lo]+(T[hi]-T[lo])*(sung.index(i)-sung.index(lo))/(sung.index(hi)-sung.index(lo))
        elif lo is not None: T[i]=T[lo]+4*(sung.index(i)-sung.index(lo))
        else: T[i]=max(0,T[hi]-4*(sung.index(hi)-sung.index(i)))
    for i in sung: d['lines'][i]['t']=round(T[i],2)
    for i,l in enumerate(d['lines']):
        if not l['text']: l['t']=d['lines'][i-1]['t']+0.01 if i else 0
    # fix order: line dicts with t first
    d['lines']=[({'t':l['t']}|{k:v for k,v in l.items() if k!='t'}) if l['text'] else {'text':''} for l in d['lines']]
    json.dump(d,open(R+key+'.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    # spot check: words transcribed within 3s after t
    chk=[]
    for i in sung[::max(1,len(sung)//5)][:6]:
        t=T[i]; near=' '.join(w for w,s in tw if t-0.3<=s<t+3)
        chk.append(f"{t:6.1f} | {d['lines'][i]['text'][:45]} || {near[:60]}")
    rep[key]=dict(direct=len(good),kept=len(ks),sung=len(sung),words=len(tw),chk=chk)
    print(key,json.dumps(rep[key],indent=1),flush=True)
