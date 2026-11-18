// Verify the offline cross-study report, filters, missing cells and local evidence links.
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),period=process.argv.includes('--period'),rel=period?'experiments/period-001':'reports/comprehensive',out=path.join(root,rel),prefix=period?'period-001':'comprehensive',entry=period?'report.html':'index.html';
 const d=JSON.parse(fs.readFileSync(path.join(out,period?'comparison.json':'results.json'),'utf8'));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(out,entry)).href);
  const rows=page.locator('#main-table tbody tr');
  if(await rows.count()!==d.rows.length)throw Error('Wrong initial row count');
  for(const r of d.rows){
   const cells=page.locator('#main-table tbody tr').filter({has:page.locator(`[data-detail="${r.id}"]`)}).locator('td');
   for(const [i,key] of ['bfcl_off','bfcl_on','he_off','he_on'].entries()){
    const text=await cells.nth(i+3).innerText(),c=r.conditions[key];
    if(c?.complete&&text!==`${c.score}/${c.expected}`)throw Error('Wrong score '+r.id+' '+key);
    if(c&&!c.complete&&text.includes('/'+c.expected))throw Error('Partial score promoted '+r.id);
   }
  }
  await page.locator('#model').selectOption('Mage-VL-Cowork');if(await rows.count()!==4)throw Error('Model filter failed');
  await page.locator('#kind').selectOption('incomplete');if(await rows.count()!==3)throw Error('Incomplete filter failed');
  await page.locator('#reset').click();await page.locator('#mtp').selectOption('on');
  if(await rows.count()!==d.rows.filter(r=>r.mtp==='on').length)throw Error('MTP filter failed');
  await page.locator('#reset').click();await page.locator('[data-sort="bfcl_off"]').click();
  if(!(await rows.first().locator('td').nth(3).innerText()).startsWith('75/80'))throw Error('Score sort failed');
  await page.locator('#search').fill('impossible-model');if(await rows.count()!==0)throw Error('Empty filter failed');
  await page.locator('#reset').click();await page.locator('[data-tab="cases"]').click();
  if(await page.locator('#heatmap tbody tr').count()!==27)throw Error('Heatmap includes speed-only');
  await page.locator('#case-key').selectOption('he_on');
  const mage=page.locator('#heatmap tbody tr').filter({hasText:'R20 Mage'});
  if(!(await mage.innerText()).includes('—'))throw Error('Missing HE shown as a grade');
  await page.locator('[data-tab="coverage"]').click();
  if(await page.locator('#coverage-table tbody tr').count()!==36)throw Error('Coverage omitted candidates');
  await page.locator('[data-tab="historical"]').click();
  if(await page.locator('#history-table tbody tr').count()!==24)throw Error('Historical rows missing');
  await page.locator('[data-tab="inventory"]').click();
  if(await page.locator('#run-table tbody tr').count()!==173)throw Error('Inventory incomplete');
  let links=0;for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href))){
   if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing link '+href);links++}
  }
  await page.locator('[data-tab="comparison"]').click();
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow '+width);
   if(width!==768)await page.screenshot({path:path.join(root,'publication',`${prefix}-${width}.png`),fullPage:true});
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={passed:true,report:rel+'/'+entry,row_count:d.rows.length,filters_and_sort_verified:true,partial_and_missing_score_labels_verified:true,heatmap_and_coverage_verified:true,old_conditions_and_run_inventory_verified:true,viewports:[1440,768,390],local_links_checked:links,errors};
  fs.writeFileSync(path.join(root,'publication',prefix+'-ui-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
