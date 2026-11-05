// Browser source copied verbatim to the offline report; no network requests.
(()=>{
 'use strict';
 const data=JSON.parse(document.querySelector('#data').textContent);
 const $=s=>document.querySelector(s),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const link=(p,label)=>`<a href="../../${esc(p)}">${esc(label)}</a>`;
 const num=(n,d=2)=>n==null?'—':Number(n).toLocaleString('en-US',{maximumFractionDigits:d});
 const keys=['bfcl_off','bfcl_on','he_off','he_on'],names=['BFCL OFF','BFCL ON','HumanEval OFF','HumanEval ON'];
 const score=c=>!c?'—':c.complete?`${c.score}/${c.expected}`:c.saved?`<span class="partial">未完了<small>保存${c.saved}・正解${c.passed_saved}</small></span>`:c.status==='failed'?'<span class="partial">失敗・応答未保存</span>':'未実施';
 let sort='index',descending=false,selected=data.rows[0].id;
 const complete=r=>Object.keys(r.conditions).length===4&&Object.values(r.conditions).every(c=>c.complete);
 function filtered(){const q=$('#search').value.toLowerCase(),m=$('#model').value,mtp=$('#mtp').value,k=$('#kind').value;return data.rows.filter(r=>(!q||JSON.stringify([r.id,r.model,r.quantization,r.placement]).toLowerCase().includes(q))&&(!m||m===r.model)&&(!mtp||mtp===r.mtp)&&(!k||(k==='complete'?complete(r):k==='incomplete'?r.kind==='quality'&&!complete(r):r.kind==='speed-only')))}
 function table(headers,rows,cls='index'){return `<table class="${cls}"><thead><tr>${headers.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>'<tr>'+r.map(x=>`<td>${x??'—'}</td>`).join('')+'</tr>').join('')}</tbody></table>`}
 function render(){let rows=filtered();const value=r=>sort==='speed'?r.fixed_speed?.tok_s:keys.includes(sort)?r.conditions[sort]?.score:sort==='index'?data.rows.indexOf(r):r[sort];rows.sort((a,b)=>{const x=value(a),y=value(b);if(x==null)return y==null?0:1;if(y==null)return -1;return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(descending?-1:1)});
  $('#shown').textContent=`表示 ${rows.length} / ${data.rows.length}行。能力4条件完了 ${rows.filter(complete).length}行。`;
  $('#main-table tbody').innerHTML=rows.map(r=>`<tr data-row="${esc(r.id)}"><td class="rowmodel"><strong>${esc(r.model)}</strong><small>${esc(r.quantization)} · ${esc(r.label)}</small></td><td>${r.mtp.toUpperCase()}</td><td>${esc(r.placement)}<small>load ${esc(r.load_mode)} / t${esc(r.threads)}・tb${esc(r.batch_threads)}</small></td>${keys.map(k=>`<td class="score">${score(r.conditions[k])}</td>`).join('')}<td class="score">${num(r.fixed_speed?.tok_s)}<small>${r.fixed_speed?`${r.fixed_speed.cases} × ${r.fixed_speed.tokens_per_case} tokens`:'固定長測定なし'}</small></td><td><span class="pill ${r.kind==='speed-only'?'speed-only':complete(r)?'complete':'failed'}">${r.kind==='speed-only'?'速度だけ':complete(r)?'4条件完了':'未完了'}</span><br><button data-detail="${esc(r.id)}">${esc(r.label)} 詳細</button></td></tr>`).join('');
  $('#main-table tbody').querySelectorAll('[data-detail]').forEach(b=>b.addEventListener('click',()=>{selected=b.dataset.detail;details()}));
  if(!rows.some(r=>r.id===selected))selected=rows[0]?.id;details();heatmap(rows);coverage();
 }
 function details(){const r=data.rows.find(r=>r.id===selected);if(!r){$('#details').innerHTML='<p class="empty">該当する測定はありません。</p>';return}
  const mem=r.memory,conds=keys.filter(k=>r.conditions[k]);
  $('#details').innerHTML=`<h3>${esc(r.label)} · ${esc(r.model)} / ${esc(r.quantization)} / MTP ${r.mtp.toUpperCase()}</h3><p class="wrap">${link(r.evidence,r.id)}<br>${esc(r.origin)}</p><p>${esc(r.placement)}。${esc(r.runtime)} / context ${num(r.context,0)} / 出力上限 ${num(r.max_output,0)} / KV ${esc(r.kv_k)}・${esc(r.kv_v)}。<br>思考制御: ${esc(r.mode_control)}。MTP制御: ${esc(r.mtp_control)}。</p><p class="note">メモリ観測範囲: ${esc(mem.scope)}。システムGPU使用ピーク ${num(mem.peak_gpu_mib,0)} MiB / 最小空きRAM ${num(mem.minimum_ram_gib)} GiB。これは標本観測であり、モデル単体の専有量ではありません。</p>${conds.length?'<div class="scroll compact">'+table(['条件','主採点','保存応答の合計秒','既知の出力上限 / 統計不明','形式エラー / 空finalで正解','問題回答中 decode tok/s','推論の観測'],conds.map(k=>{const c=r.conditions[k];return [names[keys.indexOf(k)],score(c),num(c.seconds_saved),`${c.caps_known} / ${c.unknown_statistics}`,`${c.parser_errors} / ${c.passed_without_final}`,`${num(c.benchmark_decode_tok_s)}<small>${c.decode_statistics_cases}件のtimings</small>`,`${c.reasoning_observed_known} / ${c.saved}<small>${c.expected===80?`ツール必須問題: 正解${c.tool_needed_passed} / 保存${c.tool_needed_saved}（全60問）`:''}</small>`]}))+'</div>':'<p>能力試験は実施していません。</p>'}
  ${conds.filter(k=>r.conditions[k].error).map(k=>`<p class="warning">${esc(names[keys.indexOf(k)])}: ${esc(r.conditions[k].error)}</p>`).join('')}
  ${r.secondary_he?`<p class="note">補助採点は主得点に混ぜません: ${link(r.secondary_evidence,JSON.stringify(r.secondary_he))}</p>`:''}
  <details><summary>実際のリクエスト設定・配布情報・起動条件</summary><div class="detailgrid"><div><h3>保存されたサンプラー</h3><pre>${esc(JSON.stringify(Object.fromEntries(conds.map(k=>[k,r.conditions[k].samplers])),null,2))}</pre></div><div><h3>モデル / プロファイル</h3><pre>${esc(JSON.stringify({artifact:r.artifact,model_hash:r.model_hash,profile:r.profile},null,2))}</pre></div></div></details>`;
 }
 function heatmap(rows){const key=$('#case-key').value,quality=rows.filter(r=>r.kind==='quality'),all=new Map;quality.forEach(r=>r.conditions[key]?.cases.forEach(c=>all.set(c.id,c.category)));const ids=[...all.keys()];
  $('#heatmap').innerHTML=table(['測定行 / 問題番号',...ids.map((id,i)=>`<span title="${esc(id)}">${i+1}</span>`)],quality.map(r=>{const map=new Map((r.conditions[key]?.cases||[]).map(c=>[c.id,c]));return [`${esc(r.label)} ${esc(r.model)}<br>${esc(r.quantization)} / MTP ${r.mtp.toUpperCase()}`,...ids.map(id=>{const c=map.get(id);if(!c)return '<span class="muted">—</span>';const cap=c.finish_reason==='length',cls=cap?'cap':c.passed?'ok':'bad';return `<span class="${cls}"><a title="${esc(id)}: ${c.passed?'正解':'不正解'}${cap?'・出力上限':''}${c.http_status===500?'・HTTP500形式エラー':''}" href="../../${esc(c.raw)}">${cap?'!':c.passed?'✓':'×'}</a></span>`})]}),'heat');
  $('#heatmap').querySelectorAll('td:has(.ok),td:has(.bad),td:has(.cap)').forEach(td=>td.className=td.firstElementChild.className);
  const eligible=quality.filter(r=>r.conditions[key]?.complete),failures=ids.map(id=>{const cases=eligible.map(r=>({r,c:r.conditions[key].cases.find(c=>c.id===id)})).filter(x=>x.c);return {id,cases,failed:cases.filter(x=>!x.c.passed)}}).filter(x=>x.failed.length).sort((a,b)=>b.failed.length-a.failed.length||a.id.localeCompare(b.id));
  $('#failures').innerHTML=table(['問題','失敗測定行 / 完了測定行','失敗した行'],failures.slice(0,15).map(x=>[esc(x.id),`${x.failed.length} / ${x.cases.length}`,x.failed.map(({r,c})=>link(c.raw,r.label)).join(' · ')]));
 }
 function coverage(){const q=$('#search').value.toLowerCase(),m=$('#model').value,mtp=$('#mtp').value,states={complete:'完了',partial:'保存分あり・未完了',failed:'失敗・応答未保存','not-measured':'未測定'};
  const rows=data.coverage.filter(r=>(!q||JSON.stringify([r.model,r.quantization,r.matching_rows]).toLowerCase().includes(q))&&(!m||m===r.model)&&(!mtp||mtp===r.mtp));
  $('#coverage-table').innerHTML=table(['モデル','量子化','MTP',...names,'測定行 / 補足'],rows.map(r=>[esc(r.model),esc(r.quantization),r.mtp.toUpperCase(),...keys.map(k=>states[r.states[k]]),`${r.matching_rows.map(id=>esc(data.rows.find(x=>x.id===id).label)).join(', ')||'—'}<small>${esc(r.note)}</small>`]));
 }
 function indices(){
  $('#history-table').innerHTML=table(['出典 / モデル','試験 / 思考','runtime / context','最大出力','結果','出力上限','再掲'],data.historical.map(r=>[link(r.source,r.source.split('/').slice(-2,-1)[0])+'<br>'+esc(r.model_key),`${esc(r.benchmark)} / ${esc(r.thinking)}`,esc(r.runtime)+'<br>'+esc(r.context),esc(r.max_output),r.saved===r.expected?`${r.passed_saved}/${r.expected}`:`未完了: 保存${r.saved}・正解${r.passed_saved}`,r.caps,r.same_response_snapshot?'同一応答の再掲':'—']));
  const runs=rs=>table(['run / 試験','収集状態','結果 / 補足'],rs.map(r=>[link(r.evidence,r.run)+`<small>${esc(r.benchmark)} / ${esc(r.type)}</small>`,esc(r.status),`${esc(r.headline??r.outcome??r.error)}${r.tok_s!=null?`<br>${num(r.tok_s)} tok/s (${r.attempted} × ${r.tokens_per_case} tokens)`:''}`]));
  $('#ancillary').innerHTML=Object.entries({speed:'固定長速度と短い起動プローブ',capacity:'容量・MTP利用可否・取得準備',integration:'Hermes実ツール / MCP接続',replay:'既存回答の補助採点'}).map(([k,label])=>`<details><summary>${label}（${data.ancillary[k].length}件）</summary><div class="scroll compact">${runs(data.ancillary[k])}</div></details>`).join('');
  $('#run-table').innerHTML=runs(data.inventory);$('#archives').innerHTML='<ul>'+data.archives.map(r=>`<li>${link(r.path,r.path)}<small> ${esc(r.role)}</small></li>`).join('')+'</ul>';
 }
 const c=data.counts;$('#metrics').innerHTML=[[c.configuration_rows,'測定行（速度のみ3を含む）'],[c.unique_model_quant_pairs_measured,'モデル・量子化ペア'],[c.unique_model_quant_mtp_measured,'MTPを含む組み合わせ'],[c.complete_conditions+'/'+c.condition_slots,'能力条件 完了 / 保存枠'],[c.unique_saved_responses.toLocaleString(),'重複を除く保存応答']].map(([n,label])=>`<div class="metric"><strong>${n}</strong><span>${label}</span></div>`).join('');
 [...new Set(data.rows.map(r=>r.model))].sort().forEach(m=>$('#model').add(new Option(m,m)));
 ['search','model','mtp','kind'].forEach(id=>$('#'+id).addEventListener(id==='search'?'input':'change',render));$('#case-key').addEventListener('change',()=>heatmap(filtered()));
 $('#reset').addEventListener('click',()=>{['search','model','mtp','kind'].forEach(id=>$('#'+id).value='');render()});
 document.querySelectorAll('[data-sort]').forEach(b=>b.addEventListener('click',()=>{descending=sort===b.dataset.sort?!descending:true;sort=b.dataset.sort;render()}));
 document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(x=>x.setAttribute('aria-selected',String(x===b)));['comparison','cases','coverage','historical','inventory'].forEach(id=>$('#'+id).hidden=id!==b.dataset.tab)}));
 indices();render();
})();
