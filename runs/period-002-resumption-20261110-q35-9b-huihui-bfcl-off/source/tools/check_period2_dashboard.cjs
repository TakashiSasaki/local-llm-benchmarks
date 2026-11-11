// Optional dependency-free headless Chromium QA; only opens local report files.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{pathToFileURL,fileURLToPath}=require('node:url');
const root=path.resolve(__dirname,'..'),out=path.join(root,'.local/validation/handoff-20261106');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const chrome=process.env.CHROMIUM_PATH;if(!chrome)throw Error('Set CHROMIUM_PATH to an installed Chromium executable');
(async()=>{
 fs.mkdirSync(out,{recursive:true});const profile=fs.mkdtempSync(path.join(os.tmpdir(),'period2-browser-'));
 const child=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 let ws;const pending=new Map();let next=1;
 try{
  const portfile=path.join(profile,'DevToolsActivePort');let attempts=0;
  while(!fs.existsSync(portfile)&&attempts++<150)await sleep(100);
  if(!fs.existsSync(portfile))throw Error('Owned browser did not start');
  const port=fs.readFileSync(portfile,'utf8').split('\n')[0];
  const targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  ws=new WebSocket(targets.find(x=>x.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true})});
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=next++;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.delete(id))reject(Error('CDP timeout: '+method))},10000).unref()});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
  await send('Page.enable');const results=[];
  for(const file of ['experiments/period-002/reports/index.html','index.html','reports/index.html']){
   await send('Page.navigate',{url:pathToFileURL(path.join(root,file)).href});
   for(let i=0;i<100;i++){if(await evaluate('document.readyState')==='complete')break;await sleep(50)}
   const links=await evaluate('Array.from(document.querySelectorAll("a[href]"),a=>a.href)');
   for(const href of links)if(href.startsWith('file:')&&!fs.existsSync(fileURLToPath(href)))throw Error('Missing local link: '+href);
   if(file.startsWith('experiments/')){
    const counts=await evaluate('Array.from(document.querySelectorAll("table"),t=>t.rows.length)');
    if(JSON.stringify(counts)!=='[9,13,4,5]')throw Error('Unexpected report table rows: '+JSON.stringify(counts));
    const text=await evaluate('document.body.innerText');if(!text.includes('7/8（部分・残り12）')||!text.includes('1,012'))throw Error('Missing partial/remaining labels');
   }
   for(const width of [1440,390]){
    await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
    if(await evaluate('document.documentElement.scrollWidth>innerWidth'))throw Error('Page overflow '+file+' '+width);
    if(file.startsWith('experiments/')){const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'period2-'+width+'.png'),Buffer.from(shot.data,'base64'))}
   }
   results.push({file,local_links_checked:links.filter(x=>x.startsWith('file:')).length,viewports:[1440,390]});
  }
  const result={passed:true,pages:results,model_inference_performed:false};fs.writeFileSync(path.join(out,'browser-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
  await send('Browser.close').catch(()=>{});
 }finally{if(ws)ws.close();if(child.exitCode===null){await sleep(1000);if(child.exitCode===null)child.kill()}}
})().catch(e=>{console.error(e);process.exitCode=1});
