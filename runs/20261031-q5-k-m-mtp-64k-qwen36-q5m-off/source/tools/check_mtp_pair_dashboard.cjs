// Visual and link checks for the Qwen3.6 MTP pair; no model inference.
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),prefix=process.argv[2]||'20261031-qwen36-q4-mtp-64k';
 const data=JSON.parse(fs.readFileSync(path.join(root,'reports',prefix,'matrix-data.json'),'utf8'));
 if(data.cells.length!==2||data.cells.some(c=>c.status!=='complete'))throw Error('Primary pair incomplete');
 const options={headless:true};if(process.env.CHROMIUM_PATH)options.executablePath=process.env.CHROMIUM_PATH;
 const browser=await chromium.launch(options);
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'reports',prefix,'index.html')).href);
  if(await page.locator('#main-matrix tbody tr').count()!==2)throw Error('Expected two newly measured rows');
  if(await page.locator('#reference-matrix tbody tr').count()!==data.references.length)throw Error('Reference count mismatch');
  for(const [index,cell] of data.cells.entries()){
   const rendered=page.locator('#main-matrix tbody tr').nth(index).locator('td');
   for(const [column,key] of ['bfcl_off','bfcl_on','humaneval_off','humaneval_on'].entries()){
    const metric=cell.metrics[key];
    if(await rendered.nth(column).locator('.score').innerText()!==`${metric.passed}/${metric.expected}`)throw Error('Rendered score mismatch: '+key);
   }
   if(await rendered.nth(4).innerText()!==cell.speed.median_decode_tokens_per_second.toFixed(2))throw Error('Rendered throughput mismatch');
  }
  let links=0;
  for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href))){if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing link '+href);links++}}
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Page overflow at '+width);
   if(width!==768)await page.screenshot({path:path.join(root,'publication','qwen36-q4-mtp-'+width+'.png'),fullPage:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={passed:true,report:'reports/'+prefix+'/index.html',new_rows:2,reference_rows:data.references.length,viewports:[1440,768,390],local_links_checked:links,errors};
  fs.writeFileSync(path.join(root,'publication','qwen36-q4-mtp-ui-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
