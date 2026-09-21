"use strict";
async function readJSON(path){const r=await fetch(path);if(!r.ok)throw new Error("数据文件读取失败");return r.json();}
function add(parent,tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;parent.append(el);return el;}
async function datasetPage(){
 const host=document.getElementById("samples");if(!host)return;
 try{
  const data=await readJSON("assets/samples.json");const suite=document.getElementById("suite-filter"),route=document.getElementById("route-filter"),query=document.getElementById("sample-search");
  const pageSize=30;let currentPage=0;const pager=document.createElement("div");pager.className="pagination";pager.setAttribute("aria-label","样本分页");host.before(pager);
  const previous=add(pager,"button","上一页");previous.type="button";const pageLabel=add(pager,"span","");pageLabel.setAttribute("aria-live","polite");const next=add(pager,"button","下一页");next.type="button";
  const render=()=>{host.replaceChildren();const q=query.value.trim();const rows=data.filter(r=>(!suite.value||r.suite===suite.value)&&(!route.value||r.provenance.route===route.value)&&(!q||(r.input_text+r.genre).includes(q)));const pages=Math.ceil(rows.length/pageSize);currentPage=Math.max(0,Math.min(currentPage,Math.max(0,pages-1)));const start=currentPage*pageSize;document.getElementById("sample-count").textContent=rows.length?"共 "+rows.length+" 个公开样本 · 当前显示 "+(start+1)+"—"+Math.min(start+pageSize,rows.length):"当前筛选无匹配样本";pageLabel.textContent=pages?"第 "+(currentPage+1)+" / "+pages+" 页":"无匹配页";previous.disabled=currentPage===0;next.disabled=currentPage+1>=pages;
   for(const row of rows.slice(start,start+pageSize)){const card=add(host,"article","","card sample");card.dataset.sampleId=row.id;add(card,"span",row.suite,"tag");add(card,"span",row.provenance.route==="natural"?"自然输出":"受控变体","tag");add(card,"h3",row.genre+" / "+row.stage);add(card,"p",row.instruction,"muted");add(card,"pre",row.input_text);add(card,"p","家族 "+row.source_group_id+" · "+row.locale+" · 标注状态 "+row.disagreement_status,"muted");}if(!rows.length)add(host,"p","当前筛选条件下没有公开样本。");};
  const reset=()=>{currentPage=0;render();};previous.addEventListener("click",()=>{currentPage--;render();});next.addEventListener("click",()=>{currentPage++;render();});suite.addEventListener("change",reset);route.addEventListener("change",reset);query.addEventListener("input",reset);render();
 }catch(error){host.textContent="样本暂时无法读取，请刷新后重试。";}
}
async function resultsPage(){
 const host=document.getElementById("results");if(!host)return;
 try{
  const report=await readJSON("assets/results.json");
  add(host,"p",report.summary||"正式实验尚未运行。");
  for(const item of report.statuses||[]){const p=add(host,"p","");add(p,"strong",item.label+"：");add(p,"span",item.value);}
  const groups=report.suite_results||(report.rows?.length?[{suite:"已登记实验",rows:report.rows}]:[]);
  for(const group of groups){
   const section=add(host,"section","","section");add(section,"h2",group.suite);
   if(group.note)add(section,"p",group.note,"muted");
   if(!group.rows?.length){add(section,"p","此套件尚无可发布的完整结果。");continue;}
   const scroll=add(section,"div","","table-scroll");scroll.tabIndex=0;scroll.setAttribute("role","region");scroll.setAttribute("aria-label",group.suite+"结果表，可横向滚动");
   const table=add(scroll,"table","");const head=add(table,"thead","");const tr=add(head,"tr","");
   for(const h of ["模型","方法","模式","样本路线","风格配置","登记单元","已记录单元","完成单元","有效成功/已记录","有效成功/完成","运行状态"]){const th=add(tr,"th",h);th.scope="col";}
   const body=add(table,"tbody","");
   for(const row of group.rows){const r=add(body,"tr","");for(const k of ["model","method","mode","route","profile","n","recorded","completed","success","success_given_completion","status"])add(r,"td",String(row[k]??"未运行"));}
  }
 }catch(e){host.textContent="结果文件读取失败。";}
}

datasetPage();resultsPage();
