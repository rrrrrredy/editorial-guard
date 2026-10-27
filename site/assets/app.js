"use strict";
async function readJSON(path){const r=await fetch(path);if(!r.ok)throw new Error("数据文件读取失败");return r.json();}
function add(parent,tag,text,cls){const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;parent.append(el);return el;}
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

resultsPage();
