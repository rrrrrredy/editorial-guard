"use strict";
async function familyPage(){
 const host=document.getElementById("samples");if(!host)return;
 try{
  const data=await readJSON("assets/samples.json");
  const controls=Object.fromEntries(["suite","stage","genre","status","length"].map(k=>[k,document.getElementById(k+"-filter")]));
  const query=document.getElementById("sample-search"),params=new URLSearchParams(location.search);
  const families=new Map(),published=new Map(data.map(r=>[r.id,r])),fullCache=new Map();
  for(const row of data){const key=row.suite+"/"+row.source_group_id;if(!families.has(key))families.set(key,[]);families.get(key).push(row);}
  for(const genre of [...new Set(data.map(r=>r.genre))].sort()){const o=add(controls.genre,"option",genre);o.value=genre;}
  for(const [key,control] of Object.entries(controls))control.value=params.get(key)||"";
  query.value=params.get("family")||params.get("q")||"";
  const labels={plan:"计划",progress:"进展",final:"最终交付",agreement:"指定字段一致",disputed:"有争议",insufficient_evidence:"证据不足"};
  const chars=text=>Array.from(text).length;
  const json=(parent,value)=>add(parent,"pre",JSON.stringify(value,null,2),"record-json");
  function fullRows(text){
   const rows=text.split(/\r?\n/).filter(line=>line.trim()).map(line=>JSON.parse(line));
   const accepted=new Map();
   for(const row of rows){const preview=published.get(row.id);if(!preview)continue;
    if(row.suite!==preview.suite||row.source_group_id!==preview.source_group_id||row.input_text!==preview.input_text||!row.source_bundle||!Array.isArray(row.annotation_records))throw new Error("完整记录与当前公开预览不匹配");
    if(accepted.has(row.id))throw new Error("完整记录包含重复编号");accepted.set(row.id,row);
   }
   if(!accepted.size)throw new Error("文件中没有与本页对应的完整公开记录");return accepted;
  }
  async function loadSuite(suite){
   if(!fullCache.has(suite)){
    const task=(async()=>{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
     try{const response=await fetch("https://huggingface.co/datasets/RedinGhost/"+suite+"/resolve/v0.1.1/original/samples.jsonl",{signal:controller.signal});if(!response.ok)throw new Error("完整记录读取失败");const rows=fullRows(await response.text());if(rows.size!==data.filter(r=>r.suite===suite).length)throw new Error("完整记录数量不匹配");return rows;}finally{clearTimeout(timer);}
    })();fullCache.set(suite,task);task.catch(()=>fullCache.delete(suite));
   }
   return fullCache.get(suite);
  }
  function showFull(parent,rows){
   parent.replaceChildren();add(parent,"h3","事实底稿与任务约束");
   const sources=new Set(rows.map(r=>JSON.stringify([r.source_bundle,r.constraints,r.protected_spans,r.required_claims])));
   for(const row of sources.size===1?[rows[0]]:rows){if(sources.size>1)add(parent,"h4",row.provenance.route==="natural"?"正常输出的底稿":"受控变体的底稿");
    const facts=add(parent,"ul","");for(const fact of row.source_bundle.facts||[])add(facts,"li",fact);
    if(row.source_bundle.unknowns?.length){add(parent,"h4","底稿明确的未知项");const unknowns=add(parent,"ul","");for(const item of row.source_bundle.unknowns)add(unknowns,"li",item);}
    const raw=add(parent,"details","","annotation");add(raw,"summary","查看完整底稿、约束和保护信息");json(raw,{事实底稿:row.source_bundle,约束:row.constraints,保护片段:row.protected_spans,必要信息:row.required_claims});
   }
   add(parent,"h3","逐份模型标注");add(parent,"p","以下保留各模型原有理由与标签。指定字段一致也不等于人工真值。","muted");
   for(const row of rows){const section=add(parent,"section","");add(section,"h4",(row.provenance.route==="natural"?"正常输出":"受控变体")+" · "+(labels[row.disagreement_status]||row.disagreement_status));
    for(const record of row.annotation_records){const box=add(section,"details","","annotation");const a=record.annotation||{};add(box,"summary",record.provider+" · "+record.requested_model+" · "+(a.reason||"查看原始标注"));json(box,record);}
    if(!row.annotation_records.length)add(section,"p","此记录没有可用模型标注。");
   }
  }
  const pageSize=12;let currentPage=0;const pager=document.createElement("div");pager.className="pagination";pager.setAttribute("aria-label","家族分页");host.before(pager);
  const previous=add(pager,"button","上一页");previous.type="button";const pageLabel=add(pager,"span","");pageLabel.setAttribute("aria-live","polite");const next=add(pager,"button","下一页");next.type="button";
  const render=()=>{
   host.replaceChildren();const q=query.value.trim().toLocaleLowerCase();
   const groups=[...families.values()].filter(rows=>{const r=rows[0],natural=rows.find(r=>r.provenance.route==="natural")||r,n=chars(natural.input_text),band=n<400?"short":n<1000?"medium":"long";
    return (!controls.suite.value||r.suite===controls.suite.value)&&(!controls.stage.value||r.stage===controls.stage.value)&&(!controls.genre.value||r.genre===controls.genre.value)&&(!controls.status.value||rows.some(r=>r.disagreement_status===controls.status.value))&&(!controls.length.value||band===controls.length.value)&&(!q||rows.some(r=>(r.source_group_id+" "+r.instruction+" "+r.input_text+" "+r.genre).toLocaleLowerCase().includes(q)));
   });
   const pages=Math.ceil(groups.length/pageSize);currentPage=Math.max(0,Math.min(currentPage,Math.max(0,pages-1)));const start=currentPage*pageSize;
   document.getElementById("sample-count").textContent=groups.length?groups.length+" 个源家族 · "+groups.reduce((n,rows)=>n+rows.length,0)+" 条记录 · 当前显示 "+(start+1)+"—"+Math.min(start+pageSize,groups.length)+" 个家族":"当前筛选无匹配家族";
   pageLabel.textContent=pages?"第 "+(currentPage+1)+" / "+pages+" 页":"无匹配页";previous.disabled=currentPage===0;next.disabled=currentPage+1>=pages;
   for(const rows of groups.slice(start,start+pageSize)){
    const r=rows[0],card=add(host,"details","","card family");card.dataset.family=r.source_group_id;card.dataset.suite=r.suite;
    const title=add(card,"summary","");add(title,"strong",r.suite+" / "+r.source_group_id);add(title,"span",r.genre+" · "+(labels[r.stage]||r.stage)+" · "+[...new Set(rows.map(r=>labels[r.disagreement_status]||r.disagreement_status))].join("、"),"muted");
    const body=add(card,"div","","family-body");const address=new URL(location.href);address.search=new URLSearchParams({suite:r.suite,family:r.source_group_id});address.hash="";add(body,"a","此家族的直接链接").href=address.href;
    add(body,"h3","任务要求");add(body,"p",r.instruction);
    const pair=add(body,"div","","text-pair");
    for(const row of [...rows].sort((a,b)=>(a.provenance.route==="natural"?-1:1)-(b.provenance.route==="natural"?-1:1))){const section=add(pair,"section","");add(section,"h3",row.provenance.route==="natural"?"正常模型输出":"受控变体");add(section,"p",chars(row.input_text)+" 字符 · "+(labels[row.disagreement_status]||row.disagreement_status),"muted");add(section,"pre",row.input_text);}
    if(rows.length===2&&rows[0].input_text===rows[1].input_text)add(body,"p","本家族两份文本完全相同；这不增加内容覆盖，也不自动说明文本合格。","notice");
    if(r.suite==="StyleBench-ZH"&&r.source_group_id==="main-0439"){add(body,"p","这里展示原稿与受控变体。已有候选改写扩大否定范围的例子，另见实验结果。");add(body,"a","阅读候选改写与相反裁判意见").href="https://github.com/rrrrrredy/editorial-guard/blob/main/reports/results.md#一次变得更清楚却扩大事实范围的改写";}
    const full=add(body,"div","","family-evidence");let loaded=false;
    const hydrate=async()=>{if(loaded)return;full.replaceChildren();add(full,"p","正在读取完整事实与标注…","muted");
     try{const records=await loadSuite(r.suite),selected=rows.map(row=>records.get(row.id));if(selected.some(row=>!row))throw new Error("当前载入文件缺少此家族");showFull(full,selected);loaded=true;}
     catch(error){full.replaceChildren();add(full,"p","完整记录暂不可用。可重试，或在页面上方载入已下载的 samples.jsonl；两份公开文本仍可阅读。","notice");const retry=add(full,"button","重试完整记录");retry.type="button";retry.addEventListener("click",hydrate);}
    };
    card.addEventListener("toggle",()=>{if(card.open)hydrate();});
    if(groups.length===1&&query.value===r.source_group_id)card.open=true;
   }
   if(!groups.length)add(host,"p","试试其他关键词，或清除筛选。");
  };
  const resetPage=()=>{currentPage=0;const state=new URLSearchParams();for(const [key,control] of Object.entries(controls))if(control.value)state.set(key,control.value);if(query.value.trim())state.set("q",query.value.trim());history.replaceState(null,"",location.pathname+(state.size?"?"+state:""));render();};
  previous.addEventListener("click",()=>{currentPage--;render();});next.addEventListener("click",()=>{currentPage++;render();});
  Object.values(controls).forEach(control=>control.addEventListener("change",resetPage));query.addEventListener("input",resetPage);
  document.getElementById("reset-filters").addEventListener("click",()=>{Object.values(controls).forEach(control=>control.value="");query.value="";resetPage();});
  document.getElementById("full-data-file").addEventListener("change",async event=>{const status=document.getElementById("import-status"),file=event.target.files[0];if(!file)return;
   try{const records=fullRows(await file.text());for(const suite of new Set([...records.values()].map(r=>r.suite)))fullCache.set(suite,Promise.resolve(new Map([...records].filter(([,r])=>r.suite===suite))));status.textContent="已在本机载入 "+records.size+" 条完整公开记录。";render();}catch(error){status.textContent="未载入："+error.message;}
  });render();
 }catch(error){host.textContent="样本暂时无法读取，请刷新后重试。";document.getElementById("sample-count").textContent="公开预览读取失败";}
}
familyPage();
