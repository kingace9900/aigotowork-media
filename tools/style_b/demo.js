
const PROMPT="新增兩欄，都用公式，不要直接填數字：\n1.「剩餘天數」＝截止日減今天\n2.「是否逾期」";
function lerp(a,b,x){return a+(b-a)*Math.max(0,Math.min(1,x))}
function setMouse(x,y){const m=document.getElementById('mouse');m.style.left=x+'px';m.style.top=y+'px'}
window.demoRender=function(t){
  
  
  const inp=document.getElementById('in');
  // typing 0.8-5.5
  if(t<0.8){inp.className='input';inp.innerHTML='<span class="ph">輸入提示詞…</span>'}
  else if(t<6.2){inp.className='input focus';const n=Math.floor(PROMPT.length*Math.min(1,(t-0.8)/4.6));inp.innerHTML=PROMPT.slice(0,n).replace(/\n/g,'<br>')+'<span class="cur">|</span>'}
  else {inp.className='input';inp.innerHTML='<span class="ph">輸入提示詞…</span>'}
  // mouse: idle -> input -> send
  let mx,my; if(t<0.8){mx=lerp(1300,1620,t/0.8);my=lerp(500,700,t/0.8)} else if(t<5.6){mx=1620;my=700} else if(t<6.2){mx=lerp(1620,1800,(t-5.6)/0.6);my=lerp(700,790,(t-5.6)/0.6)} else {mx=lerp(1800,1200,(t-6.2)/1.5);my=lerp(790,520,(t-6.2)/1.5)}
  setMouse(mx,my);
  const r=document.getElementById('ring'); if(t>6.0&&t<6.6){r.style.display='block';r.style.left=(1800-12)+'px';r.style.top=(790-12)+'px'} else r.style.display='none';
  document.getElementById('m1').classList.toggle('hide',t<6.2);
  document.getElementById('m2').classList.toggle('hide',t<7.4);
  // columns fill 7.4-9.4
  const rows=[...document.querySelectorAll('#tb tr')];
  rows.forEach((tr,i)=>{tr.querySelectorAll('.c5,.c6').forEach(c=>{const show=(i==0)?t>=7.4:t>=7.4+i*0.3; c.classList.toggle('hide',!show); c.classList.toggle('new',i>0&&show&&t<11.5)})});
  const k=document.getElementById('kpi');k.classList.toggle('hide',t<9.6);
  document.getElementById('pct').textContent=Math.round(lerp(0,33,(t-9.6)/0.8))+'%';
  document.getElementById('late').className=t>=10.4?'r':'';
}
