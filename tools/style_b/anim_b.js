var SC=[];
function clamp(v){return Math.max(0,Math.min(1,v))}
window.initB=function(a){var durs=a[0],demo=a[1];
 document.querySelectorAll('.scene').forEach(function(s,i){
  var c=s.querySelector('.c'); var tg=[];
  if(c&&!demo[i]){
   for(var ch of c.children){
    if(ch.tagName=='TABLE'){tg.push(...ch.querySelectorAll('tr'))}
    else if(ch.tagName=='UL'||ch.tagName=='OL'){tg.push(...ch.children)}
    else if(ch.classList.contains('cols')||ch.classList.contains('steps')){tg.push(...ch.children)}
    else tg.push(ch);
   }
  }
  var d=durs[i], n=tg.length, gap=n?Math.min(1.1,(0.55*d)/n):0;
  var items=tg.map(function(el,k){var pr=el.classList&&el.classList.contains('prompt')?el:(el.querySelector?el.querySelector('.prompt'):null);
    var o={el:el,t:0.25+k*gap}; if(pr){o.pr=pr;o.txt=pr.textContent;o.tt=Math.min(3.2,0.4*d)} return o});
  var end=0; items.forEach(function(o){end=Math.max(end,o.t+0.35,o.pr?o.t+o.tt:0)}); if(demo[i]) end=12.5;
  SC.push({el:s,items:items,dur:d,demo:demo[i],hero:s.classList.contains('hero'),end:end});
 }); return SC.map(function(x){return x.end});};
window.renderB=function(si,lt,face,cap,prog){
 SC.forEach(function(s,i){s.el.style.display=(i==si)?'block':'none'});
 var s=SC[si]; document.body.classList.toggle('isHero',s.hero);
 if(s.demo){demoRender(lt)}
 s.items.forEach(function(it){var o=clamp((lt-it.t)/0.35); it.el.style.opacity=o; it.el.style.transform='translateY('+((1-o)*18)+'px)';
   if(it.pr){var f=clamp((lt-it.t)/it.tt), m=Math.floor(it.txt.length*f); it.pr.innerHTML=it.txt.slice(0,m).replace(/&/g,'&amp;').replace(/</g,'&lt;')+(f<1?'<span class="cur">|</span>':'')}});
 [0,1,2,3].forEach(function(k){document.getElementById('i'+k).style.opacity=(k==face?1:0)});
 document.getElementById('bub').innerHTML=cap;
 document.getElementById('prog').style.width=(prog*100)+'%';
};
