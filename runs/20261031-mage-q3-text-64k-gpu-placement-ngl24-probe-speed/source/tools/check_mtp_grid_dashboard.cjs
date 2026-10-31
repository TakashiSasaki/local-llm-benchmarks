// Saved-data rendering, filtering, local links and responsive layout; no inference.
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),prefix=process.argv[2];
 if(!prefix||!/^[A-Za-z0-9._-]+$/.test(prefix))throw Error('Supply one run ID');
 const data=JSON.parse(fs.readFileSync(path.join(root,'reports',prefix,'matrix-data.json'),'utf8'));
 if(data.status!=='complete'||data.cells.some(c=>c.status!=='complete'))throw Error('Collection incomplete');
 const options={headless:true};if(process.env.CHROMIUM_PATH)options.executablePath=process.env.CHROMIUM_PATH;
 const browser=await chromium.launch(options);
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'reports',prefix,'index.html')).href);
  const rows=page.locator('#main-matrix tbody tr');
  if(await rows.count()!==data.cells.length)throw Error('Wrong number of measured/reference rows');
  for(const [index,cell] of data.cells.entries()){
   const rendered=rows.nth(index).locator('td');
   for(const [column,key] of ['bfcl_off','bfcl_on','humaneval_off','humaneval_on'].entries()){
    const metric=cell.metrics[key];
    if(!(await rendered.nth(column).innerText()).startsWith(`${metric.passed}/${metric.expected}`))throw Error('Wrong score '+cell.run+' '+key);
   }
   if(await rendered.nth(4).innerText()!==cell.speed.median_decode_tokens_per_second.toFixed(2))throw Error('Wrong throughput');
  }
  await page.locator('#filter').fill('no-such-model-unique-filter');
  if(await page.locator('#main-matrix tbody tr:visible').count()!==0)throw Error('Filter failed');
  await page.locator('#filter').fill('');
  if(await page.locator('#main-matrix tbody tr:visible').count()!==data.cells.length)throw Error('Filter reset failed');
  let links=0;
  for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href))){if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing link '+href);links++}}
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow at '+width);
   if(width!==768)await page.screenshot({path:path.join(root,'publication',prefix+'-'+width+'.png'),fullPage:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={passed:true,report:'reports/'+prefix+'/index.html',rows:data.cells.length,unavailable_conditions:data.unavailable.length,viewports:[1440,768,390],local_links_checked:links,errors};
  fs.writeFileSync(path.join(root,'publication',prefix+'-ui-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
