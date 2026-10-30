// Optional browser QA. Requires Playwright; viewer/score verification do not.
const fs=require('node:fs'),path=require('node:path');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),out=path.join(root,'publication');
 const options={headless:true};if(process.env.CHROMIUM_PATH)options.executablePath=process.env.CHROMIUM_PATH;
 const browser=await chromium.launch(options);
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(root,'reports/2026-10-30-matrix/index.html')).href);
  if(await page.locator('#matrix tr').count()!==8)throw Error('Expected 8 rows');
  if(await page.locator('#matrix td').count()!==40)throw Error('Expected 32 condition cells plus names');
  if((await page.locator('#condition-count').textContent())!=='32 / 32')throw Error('Incomplete data');
  for(const name of ['応答時間','最長応答','合計時間','生成速度','打ち切り','成功率'])await page.getByRole('button',{name,exact:true}).click();
  let localLinks=0;
  const models=await page.locator('#model-select option').evaluateAll(os=>os.map(o=>o.value));
  for(const model of models){
   await page.locator('#model-select').selectOption(model);
   for(const suite of ['he','bfcl']){
    await page.locator('#suite-select').selectOption(suite);
    if(await page.locator('#cases tr').count()!==(suite==='he'?20:80))throw Error('Case count');
    const hrefs=await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href));
    for(const href of hrefs){if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing link: '+href);localLinks++}}
   }
  }
  await page.locator('#model-select').selectOption('lfm');
  if(!(await page.locator('#mode-note').textContent()).includes('思考予算0'))throw Error('Missing LFM2.5 mode qualification');
  await page.locator('#model-select').selectOption('qwen-large');
  await page.locator('#suite-select').selectOption('bfcl');
  await page.locator('#differences').check();
  if(await page.locator('#cases tr').count()!==8)throw Error('Expected 4 improved + 4 regressed Qwen cases');
  await page.locator('#differences').uncheck();
  await page.locator('#cases details summary').first().click();
  if(await page.locator('#cases details').first().getAttribute('open')===null)throw Error('Expansion');
  await page.locator('#cases details summary').first().click();
  await page.screenshot({path:path.join(out,'dashboard-desktop.png'),fullPage:true});
  const desktopOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(out,'dashboard-mobile.png'),fullPage:true});
  const mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(errors.length||desktopOverflow||mobileOverflow)throw Error(JSON.stringify({errors,desktopOverflow,mobileOverflow}));
  const runs=fs.readdirSync(path.join(root,'runs')).filter(n=>fs.existsSync(path.join(root,'runs',n,'manifest.json'))).map(n=>JSON.parse(fs.readFileSync(path.join(root,'runs',n,'manifest.json'),'utf8'))).filter(m=>m.kind!=='replay');
  const pages=['index.html','reports/index.html',...runs.filter(m=>!m.report).map(m=>'reports/'+m.run_id+'/index.html')];
  for(const file of pages){
   await page.goto(pathToFileURL(path.join(root,file)).href);
   if(['index.html','reports/index.html'].includes(file)&&await page.locator('tbody tr').count()!==runs.length)throw Error('Run catalog count');
   for(const width of [1400,390]){
    await page.setViewportSize({width,height:844});
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error(file+' overflows at '+width);
   }
   for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href))){if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Missing catalog/evidence link: '+href);localLinks++}}
  }
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);
  await page.setViewportSize({width:1400,height:1100});await page.screenshot({path:path.join(out,'catalog-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'catalog-mobile.png'),fullPage:true});
  let addedMatrices=0;
  for(const m of runs.filter(m=>m.report&&m.report!=='reports/2026-10-30-matrix/index.html')){
   await page.goto(pathToFileURL(path.join(root,m.report)).href);
   if(!await page.locator('#benchmark-data').count())continue;
   const data=JSON.parse(await page.locator('#benchmark-data').textContent());addedMatrices++;
   if(await page.locator('#matrix tr').count()!==data.models.length)throw Error('Expanded matrix rows');
   if(await page.locator('#condition-count').textContent()!==`${data.conditions_complete} / ${data.conditions_expected}`)throw Error('Expanded condition count');
   for(const model of data.models){for(const suite of ['he','bfcl']){
    await page.locator('#model-select').selectOption(model.key);await page.locator('#suite-select').selectOption(suite);await page.locator('#differences').uncheck();
    if(await page.locator('#cases tr').count()!==(suite==='he'?20:80))throw Error('Expanded case rows');
    for(const href of await page.locator('a[href]').evaluateAll(as=>as.map(a=>a.href))){if(href.startsWith('file:')){if(!fs.existsSync(fileURLToPath(href)))throw Error('Expanded evidence link: '+href);localLinks++}}
   }}
   await page.locator('#model-select').selectOption('qwen-large-iq3m');
   await page.setViewportSize({width:1400,height:1100});await page.screenshot({path:path.join(out,'quantization-desktop.png'),fullPage:true});
   await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'quantization-mobile.png'),fullPage:true});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Expanded mobile overflow');
  }
  if(errors.length)throw Error(JSON.stringify(errors));
  const result={passed:true,browser:await browser.version(),playwright:require('playwright/package.json').version,models:8,conditions:32,added_comparison_matrices:addedMatrices,all_model_suite_views_checked:16,catalog_runs:runs.length,catalog_and_integration_pages:pages.length,local_link_checks:localLinks,js_errors:errors,desktop_overflow:desktopOverflow,mobile_overflow:mobileOverflow};
  fs.writeFileSync(path.join(out,'ui-validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
