"use strict";
async function articlePage(){
 const choice=document.getElementById("article-case");if(!choice)return;
 const status=document.getElementById("article-status");
 try{
  const cases=await readJSON("assets/cases.json");
  const labels={original:"原文",brief:"简短提示 · 首次输出","previous-skill":"旧 Skill · 首次输出","updated-skill":"新 Skill 初稿 · 首次输出",edited:"后续修订示范 · 非首次输出"};
  const controls=["left","right"].map(side=>({select:document.getElementById("article-"+side),text:document.getElementById("article-"+side+"-text")}));
  for(const control of controls)for(const [value,label] of Object.entries(labels))add(control.select,"option",label).value=value;
  controls[0].select.value="original";controls[1].select.value="edited";
  const initial=new URLSearchParams(location.search).get("case");if(cases.some(c=>c.id===initial))choice.value=initial;
  function render(){
   const item=cases.find(c=>c.id===choice.value);
   for(const control of controls)control.text.textContent=item.texts[control.select.value];
   for(const note of document.querySelectorAll("[data-case-notes]"))note.hidden=note.dataset.caseNotes!==item.id;
   status.textContent="来源记录 "+item.source.id+" · 左右均为完整正文，可切换方法。";
   history.replaceState(null,"",location.pathname+"?case="+item.id);
  }
  choice.addEventListener("change",render);for(const control of controls)control.select.addEventListener("change",render);render();
 }catch(error){status.textContent="完整案例暂时无法读取，请刷新后重试。";}
}
articlePage();
