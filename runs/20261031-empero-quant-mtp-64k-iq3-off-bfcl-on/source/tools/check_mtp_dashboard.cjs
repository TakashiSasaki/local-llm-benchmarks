// Optional visual QA for the quantization/MTP report; no model inference.
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),prefix=process.argv[2]||'20261031-empero-quant-mtp-64k';
 const options={headless:true};if(process.env.CHROMIUM_PATH)options.executablePath=process.env.CHROMIUM_PATH;
 const browser=await chromium.launch(options);
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'reports',prefix,'index.html')).href);
  if(await page.locator('tbody tr').count()!==4)throw Error('Expected four quantization/MTP rows');
  let links=0;
  for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href))){if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing link '+href);links++}}
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Page overflow at '+width);
   if(width!==768)await page.screenshot({path:path.join(root,'publication','mtp-'+width+'.png'),fullPage:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={passed:true,report:'reports/'+prefix+'/index.html',rows:4,viewports:[1440,768,390],local_links_checked:links,errors};
  fs.writeFileSync(path.join(root,'publication','mtp-ui-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
