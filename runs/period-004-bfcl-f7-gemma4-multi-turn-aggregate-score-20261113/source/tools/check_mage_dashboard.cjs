// Verify incomplete scores, throughput, local evidence links and responsive rendering.
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),prefix='20261031-mage-text-64k';
 const data=JSON.parse(fs.readFileSync(path.join(root,'reports',prefix,'results.json'),'utf8'));
 if(data.collection_status!=='incomplete')throw Error('Incomplete collection was promoted');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'reports',prefix,'index.html')).href);
  const rows=page.locator('#capability tbody tr');if(await rows.count()!==2)throw Error('Wrong capability rows');
  if(!(await rows.nth(0).innerText()).includes('未完了')||(await rows.nth(0).innerText()).includes('7/80'))throw Error('Partial Q4 shown as full accuracy');
  for(const [i,s] of data.q3_bfcl.entries())if(await rows.nth(1).locator('td').nth(i+1).innerText()!==`${s.passed}/80`)throw Error('Wrong BFCL score');
  for(const [i,s] of data.fixed_length_speed.entries())if(await page.locator('#speed tbody tr').nth(i).locator('td').nth(4).innerText()!==s.tok_s.toFixed(2))throw Error('Wrong speed');
  let links=0;
  for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href)))if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing link '+href);links++}
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow at '+width);
   if(width!==768)await page.screenshot({path:path.join(root,'publication',prefix+'-'+width+'.png'),fullPage:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={passed:true,report:'reports/'+prefix+'/index.html',incomplete_collection_label_verified:true,viewports:[1440,768,390],local_links_checked:links,errors};
  fs.writeFileSync(path.join(root,'publication',prefix+'-ui-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
