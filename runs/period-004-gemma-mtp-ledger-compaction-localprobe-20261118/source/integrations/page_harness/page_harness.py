"""Bounded search and reread harness; page text is untrusted data."""
import json, re, hashlib
from pathlib import Path
from urllib.parse import urlsplit

CHUNK=2400
MAX_PAGE=1000000
STOPWORDS={'the','and','for','with','from','this','that','what','when','where','which','does','are','was','into','how','did','who','is','of','in','to','a','an'}

class PageStore:
    def __init__(self, directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True);self.pages={}
    def add(self,url,text,metadata=None):
        if not isinstance(text,str) or not text:raise ValueError('empty page')
        if len(text)>MAX_PAGE:raise ValueError('page exceeds local page limit')
        pid='page_'+str(len(self.pages)+1); headings=[]
        for m in re.finditer(r'(?m)^\s{0,3}(#{1,6})\s+(.{1,180})$',text):
            headings.append({'heading':m.group(2).strip(),'offset':m.start()})
        page={'id':pid,'url':url,'text':text,'headings':headings,'sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'metadata':metadata or {}}
        self.pages[pid]=page
        (self.directory/(pid+'.json')).write_text(json.dumps(page,ensure_ascii=False,indent=2),encoding='utf-8')
        return {'page_id':pid,'url':url,'characters':len(text),'sha256':page['sha256'],'headings':headings[:30], 'outline_truncated':len(headings)>30,'read_hint':'Use read_page with an offset, find_in_page to search, or page_outline to see more headings.'}
    def outline(self,pid,start=0):
        p=self.pages[pid]
        if type(start) is not int or start<0 or start>len(p['headings']):raise ValueError('invalid heading index')
        end=min(start+30,len(p['headings']))
        return {'page_id':pid,'url':p['url'],'heading_index':start,'headings':p['headings'][start:end],'next_heading_index':end if end<len(p['headings']) else None}
    @staticmethod
    def section(page,offset):
        prior=[h for h in page['headings'] if h['offset']<=offset]
        return prior[-1] if prior else None
    def read(self,pid,offset):
        p=self.pages[pid]
        if type(offset) is not int or offset<0 or offset>=len(p['text']):raise ValueError('invalid offset')
        end=min(offset+CHUNK,len(p['text']))
        return {'page_id':pid,'url':p['url'],'offset':offset,'end':end,'next_offset':end if end<len(p['text']) else None,'section':self.section(p,offset),'content':p['text'][offset:end]}
    def find(self,pid,query):
        p=self.pages[pid]
        if not isinstance(query,str) or not query.strip() or len(query)>200:raise ValueError('invalid query')
        matches=[]
        for m in re.finditer(re.escape(query),p['text'],re.I):
            start=max(0,m.start()-120);end=min(len(p['text']),m.end()+180)
            matches.append({'offset':m.start(),'read_offset':max(0,m.start()-300),'section':self.section(p,m.start()),'excerpt_offset':start,'excerpt_end':end,'excerpt':p['text'][start:end]})
            if len(matches)>=8:break
        mode='exact'
        if not matches:
            # Lexical fallback is deliberately labelled: candidate relevance is not proof.
            terms=[]
            for word in re.findall(r'[A-Za-z0-9_][A-Za-z0-9_.-]*|[\u3040-\u30ff\u3400-\u9fff]{2,}',query):
                token=word.strip('._-').lower()
                if len(token)>=2 and token not in STOPWORDS and token not in terms:terms.append(token)
            terms=terms[:12]; candidates=[]
            if terms:
                for start in range(0,len(p['text']),1200):
                    end=min(start+1600,len(p['text'])); window=p['text'][start:end]
                    found=[w for w in terms if re.search(re.escape(w),window,re.I)]
                    if not found:continue
                    first=min(re.search(re.escape(w),window,re.I).start() for w in found)+start
                    candidates.append((-len(found),start,first,found))
                for _,start,first,found in sorted(candidates)[:5]:
                    excerpt_start=max(start,first-100);excerpt_end=min(len(p['text']),first+200)
                    matches.append({'offset':first,'read_offset':start,'section':self.section(p,first),'matched_terms':found,'excerpt_offset':excerpt_start,'excerpt_end':excerpt_end,'excerpt':p['text'][excerpt_start:excerpt_end]})
            mode='ranked_terms'
        result={'page_id':pid,'url':p['url'],'query':query,'mode':mode,'matches':matches,'limit':8}
        if mode=='ranked_terms':result['hint']='Approximate keyword candidates only; inspect the passage and verify the claim before citing.'
        if not matches:result['hint']='No lexical match. Try shorter distinctive words or read an outline section.'
        return result

def compact(messages,limit=18000,keep=3):
    """Evict old retrieved text, keeping tool IDs, source and reread positions."""
    if keep<1:raise ValueError('at least one recent page excerpt must remain visible')
    changed=[]
    def size():return sum(len(x.get('content') or '') for x in messages if x.get('role')=='tool')
    # A single assistant message may issue several tool calls. Keep all newly
    # returned excerpts until the model has seen them at least once.
    eligible=[m for m in messages if m.get('role')=='tool' and m.get('_page_read') and not m.get('_unseen')]
    for m in eligible[:-keep] if keep else eligible:
        if size()<=limit:break
        if m.get('_compacted'):continue
        ref=m['_page_read'];m['content']=json.dumps({'notice':'Earlier page excerpt compacted; use the saved page and offset or query to retrieve it again.',**ref},ensure_ascii=False);m['_compacted']=True;changed.append(ref)
    return changed

def audit_citations(answer,pages,read_pages,search_urls):
    """Classify cited URLs by exposure; never infer a source supports a claim."""
    def canonical(u):
        p=urlsplit(u)
        return (p.scheme.lower(),(p.hostname or '').lower(),p.path.rstrip('/'),p.query)
    opened={canonical(p['url']):pid for pid,p in pages.items()}
    searched={canonical(u) for u in search_urls}
    citations=[]
    for match in re.finditer(r'https?://[^\s<>"\'\[\]]+',answer):
        url=match.group(0).rstrip('.,;:!?]')
        while url.endswith(')') and url.count(')')>url.count('('):url=url[:-1]
        pid=opened.get(canonical(url))
        state=('read_page' if pid in read_pages else 'opened_unread') if pid else ('search_only' if canonical(url) in searched else 'unknown')
        citations.append({'url':url,'state':state,'page_id':pid})
    ids=sorted({m.group(0) for m in re.finditer(r'\bpage_\d+\b',answer)})
    page_id_references=[{'page_id':pid,'url':pages[pid]['url'],'read':pid in read_pages} for pid in ids if pid in pages]
    warnings=[]
    if not any(x['state']=='read_page' for x in citations):warnings.append('No read-page URL appears in final answer')
    if any(x['state'] in ('search_only','opened_unread','unknown') for x in citations):warnings.append('At least one cited URL was not read as a saved-page passage')
    return {'urls':citations,'page_id_references':page_id_references,'warnings':warnings,
            'scope':'Checks exposure only; does not verify whether any source supports a claim or quote.'}

class MCP:
    def __init__(self,url,session,record):
        u=urlsplit(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('MCP endpoint must be a clean HTTPS URL')
        self.url=url;self.s=session;self.s.trust_env=False;self.s.headers.update({'Accept':'application/json, text/event-stream'});self.i=0;self.record=record
    def rpc(self,method,params=None,timeout=90):
        self.i+=1;payload={'jsonrpc':'2.0','id':self.i,'method':method,'params':params or {}}
        r=self.s.post(self.url,json=payload,timeout=timeout,allow_redirects=False)
        if r.status_code in (401,403,429):raise BackendStop(f'MCP HTTP {r.status_code}; stop without retry')
        r.raise_for_status()
        if 'Mcp-Session-Id' in r.headers:self.s.headers['Mcp-Session-Id']=r.headers['Mcp-Session-Id']
        if len(r.content)>2*1024*1024:raise ValueError('MCP response too large')
        j=r.json()
        if j.get('id')!=self.i or 'error' in j or not isinstance(j.get('result'),dict):raise ValueError('MCP protocol error')
        return j['result']
    def connect(self):
        x=self.rpc('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'local-page-harness','version':'1'}})
        if x.get('protocolVersion')!='2025-11-25':raise ValueError('MCP protocol mismatch')
        self.s.headers['MCP-Protocol-Version']='2025-11-25'
        r=self.s.post(self.url,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=20,allow_redirects=False);r.raise_for_status()
        tools=self.rpc('tools/list').get('tools',[]);self.record({'type':'mcp_setup','server':x.get('serverInfo'),'tools':tools})
        return {x['name'] for x in tools}
    def call(self,name,args):
        x=self.rpc('tools/call',{'name':name,'arguments':args})
        if x.get('isError'):
            details=json.dumps(x.get('structuredContent') or x.get('content'),ensure_ascii=False)[:1000]
            if re.search(r'RATE.?LIMIT|UNAUTHORIZED|FORBIDDEN|\b429\b',details,re.I):raise BackendStop('MCP tool access/rate-limit failure: '+details)
            raise RuntimeError('MCP tool error: '+details)
        v=x.get('structuredContent')
        if not isinstance(v,dict):raise ValueError('MCP structured content missing')
        return v

class BackendStop(Exception):
    """A non-retriable service/budget failure that stops the run."""

def fetch_snapshot(client,url):
    """Read a stable server snapshot completely; do not silently truncate."""
    first=client.call('md',{'url':url,'filter_type':'raw','chunk_size':20000})
    doc=first['document_id'];total=first['total_chars']
    if not isinstance(total,int) or not 0<total<=MAX_PAGE:raise ValueError('page size exceeds limit')
    pieces=[];offset=0;cur=first
    while True:
        if cur.get('document_id')!=doc or cur.get('total_chars')!=total or cur.get('offset')!=offset:raise ValueError('snapshot/offset mismatch')
        part=cur.get('content');
        if not isinstance(part,str) or not part:raise ValueError('empty document chunk')
        pieces.append(part);offset+=len(part)
        if not cur.get('has_more'):break
        if cur.get('next_offset')!=offset or offset>=total:raise ValueError('invalid document pagination')
        cur=client.call('read_document',{'document_id':doc,'offset':offset,'chunk_size':20000})
    if offset!=total:raise ValueError('incomplete document')
    return ''.join(pieces),{'document_id':doc,'source_url':first.get('source_url'),'total_chars':total}
