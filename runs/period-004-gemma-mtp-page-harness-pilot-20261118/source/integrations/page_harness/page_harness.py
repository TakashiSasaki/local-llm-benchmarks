"""Bounded search and reread harness; page text is untrusted data."""
import json, re, hashlib
from pathlib import Path
from urllib.parse import urlsplit

CHUNK=2400
MAX_PAGE=1000000

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
        return {'page_id':pid,'url':url,'characters':len(text),'sha256':page['sha256'],'headings':headings[:50], 'outline_truncated':len(headings)>50,'read_hint':'Use read_page with an offset, or find_in_page to search this saved page.'}
    def read(self,pid,offset):
        p=self.pages[pid]
        if type(offset) is not int or offset<0 or offset>=len(p['text']):raise ValueError('invalid offset')
        end=min(offset+CHUNK,len(p['text']))
        return {'page_id':pid,'url':p['url'],'offset':offset,'end':end,'next_offset':end if end<len(p['text']) else None,'content':p['text'][offset:end]}
    def find(self,pid,query):
        p=self.pages[pid]
        if not isinstance(query,str) or not query.strip() or len(query)>200:raise ValueError('invalid query')
        matches=[]
        for m in re.finditer(re.escape(query),p['text'],re.I):
            start=max(0,m.start()-120);end=min(len(p['text']),m.end()+180)
            matches.append({'offset':m.start(),'read_offset':max(0,m.start()-300),'excerpt':p['text'][start:end]})
            if len(matches)>=8:break
        return {'page_id':pid,'url':p['url'],'query':query,'matches':matches,'limit':8}

def compact(messages,limit=18000,keep=3):
    """Evict old retrieved text, keeping tool IDs, source and reread positions."""
    changed=[]
    def size():return sum(len(x.get('content') or '') for x in messages if x.get('role')=='tool')
    eligible=[m for m in messages if m.get('role')=='tool' and m.get('_page_read')]
    for m in eligible[:-keep] if keep else eligible:
        if size()<=limit:break
        if m.get('_compacted'):continue
        ref=m['_page_read'];m['content']=json.dumps({'notice':'Earlier page excerpt compacted; reread from saved page with read_page.',**ref},ensure_ascii=False);m['_compacted']=True;changed.append(ref)
    return changed

class MCP:
    def __init__(self,url,session,record):
        u=urlsplit(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('MCP endpoint must be a clean HTTPS URL')
        self.url=url;self.s=session;self.s.trust_env=False;self.s.headers.update({'Accept':'application/json, text/event-stream'});self.i=0;self.record=record
    def rpc(self,method,params=None,timeout=90):
        self.i+=1;payload={'jsonrpc':'2.0','id':self.i,'method':method,'params':params or {}}
        r=self.s.post(self.url,json=payload,timeout=timeout,allow_redirects=False);r.raise_for_status()
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
        if x.get('isError'):raise RuntimeError('MCP tool error: '+json.dumps(x.get('structuredContent') or x.get('content'),ensure_ascii=False)[:1000])
        v=x.get('structuredContent')
        if not isinstance(v,dict):raise ValueError('MCP structured content missing')
        return v

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
