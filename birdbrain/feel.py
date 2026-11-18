"""What the list does back when it's touched: every input is answered by something you can see.

On Glass, at the Full motion level:
- a ripple of light spreads from where a card lands, is ticked off, or is added;
- a soft sheen follows the pointer across the card under it.

In both layouts, at Full and Subtle:
- ticking draws the check before the card leaves for Completed;
- a card added by quick write drops into its place;
- the status dot breathes slowly while Birdbrain is idle (faster while it scans);
- the tick box gives a little under the pointer.

Focus gets the same answers, quieter: no ripple, no sheen, smaller movements. Subtle drops the ripple and the sheen.
Off stops everything (motion.py).

The ripple and the sheen are tuned by the five variables at the top of CSS, and switched by lively() in JS.

CSS and JS are included in the list page by report.py; the script runs inside the page's own closure.
"""

CSS = """
/* what the list does back (feel.py). Ripple and sheen: Glass at Full only. Tune them here. */
:root{--ripple-size:560px;--ripple-time:950ms;--ripple-light:.4;--sheen-size:380px;--sheen-light:.1;
 --tick-cover:var(--text);--breath:.07}
:root[data-layout=glass]{--tick-cover:#fff;--breath:.14}
.row{position:relative}
.ripple{position:fixed;left:0;top:0;z-index:38;pointer-events:none}
.ripple i{position:absolute;left:calc(var(--ripple-size)/-2);top:calc(var(--ripple-size)/-2);width:var(--ripple-size);height:var(--ripple-size);
 border-radius:50%;opacity:0;will-change:transform,opacity;
 background:radial-gradient(closest-side,transparent 60%,rgba(255,255,255,calc(var(--ripple-light)*.4)) 67%,rgba(255,255,255,var(--ripple-light)) 71%,transparent 78%);
 animation:ripple var(--ripple-time) var(--m-out) both}
.ripple i:first-child{background:radial-gradient(closest-side,rgba(255,255,255,calc(var(--ripple-light)*.9)),transparent 72%);
 animation-name:ripple-glow;animation-duration:calc(var(--ripple-time)*.5)}
.ripple i:last-child{animation-delay:calc(var(--ripple-time)*.16);animation-duration:calc(var(--ripple-time)*1.12)}
@keyframes ripple{from{transform:scale(.06);opacity:1}55%{opacity:.5}to{transform:scale(1);opacity:0}}
@keyframes ripple-glow{from{transform:scale(.08);opacity:.9}to{transform:scale(.34);opacity:0}}
#sheen{position:absolute;inset:0;overflow:hidden;border-radius:inherit;pointer-events:none;opacity:0;transition:opacity var(--m-slow) var(--m-out)}
#sheen.on{opacity:1}
#sheen i{position:absolute;left:calc(var(--sheen-size)/-2);top:calc(var(--sheen-size)/-2);width:var(--sheen-size);height:var(--sheen-size);
 border-radius:50%;background:radial-gradient(closest-side,rgba(255,255,255,var(--sheen-light)),transparent);will-change:transform}
/* ticking: the box gives under the pointer, then the check is drawn on the card that lifts away */
.tick{position:relative;overflow:hidden;transition:transform var(--m-fast) var(--m-out)}
.tick:active{transform:scale(.86)}
.fly .tick:checked{animation:tick-pop var(--m-spring-time) var(--m-spring)}
.fly .tick:checked::before{content:"";position:absolute;inset:-1px;background:var(--tick-cover);transform:translateX(110%);
 animation:tick-draw var(--m-slow) var(--m-move) both}
@keyframes tick-draw{from{transform:none}to{transform:translateX(110%)}}
@keyframes tick-pop{from{transform:scale(.8)}}
/* idle, the status dot breathes */
:root[data-motion=full] .status.idle .dot{animation:dot-rest 5.2s ease-in-out infinite}
@keyframes dot-rest{0%,100%{transform:scale(calc(1 - var(--breath)));opacity:.6}50%{transform:scale(calc(1 + var(--breath)));opacity:1}}
"""

JS = r"""
/* ---- What the list does back (feel.py) ----------------------------------------------------------------------- */
function lively(){return root.dataset.layout==='glass'&&root.dataset.motion==='full';}   /* ripple and sheen: Glass, at Full */
window.birdbrainRipples=0;
function rippleAt(x,y){if(!lively())return;var el=document.createElement('div');el.className='ripple';el.setAttribute('aria-hidden','true');
  el.style.transform='translate('+Math.round(x)+'px,'+Math.round(y)+'px)';
  for(var n=0;n<3;n++)el.appendChild(document.createElement('i'));
  el.lastChild.addEventListener('animationend',function(){el.remove();});
  document.body.appendChild(el);window.birdbrainRipples++;setTimeout(function(){el.remove();},4000);}
function rippleOn(el){if(!el||!lively())return;var r=el.getBoundingClientRect();
  if(r.width&&r.bottom>0&&r.top<innerHeight)rippleAt(r.left+r.width/2,r.top+r.height/2);}
/* a card that was just added drops into its place, and the glass answers */
function dropIn(row){if(!row||CALM.matches)return;var glass=root.dataset.layout==='glass';
  row.animate([{transform:glass?'translateY(-22px) scale(1.05)':'translateY(-10px)',opacity:0},{opacity:1,offset:.4},{transform:'none',opacity:1}],
    {duration:MS.spring,easing:EASE.spring});
  setTimeout(function(){rippleOn(row);},MS.spring*.4);}
on('change','.row[data-id] .tick',function(box){if(box.checked&&LIVE)rippleOn(box);});
/* the sheen: one soft light, moved (never repainted) to follow the mouse over the card under it */
var sheen=null,sheenBox=null,sheenSeen=0,sheenRaf=0,sheenX=0,sheenY=0;
function sheenOff(){if(sheen)sheen.classList.remove('on');}
function sheenPaint(){sheenRaf=0;if(sheen)sheen.firstChild.style.transform='translate3d('+sheenX+'px,'+sheenY+'px,0)';}
wrap.addEventListener('pointermove',function(ev){
  if(ev.pointerType!=='mouse'||!lively()||(drag&&drag.active)||carry)return sheenOff();
  var row=ev.target.closest&&ev.target.closest('.bands .row[data-id]');if(!row)return sheenOff();
  if(!sheen){sheen=document.createElement('span');sheen.id='sheen';sheen.setAttribute('aria-hidden','true');sheen.appendChild(document.createElement('i'));}
  if(sheen.parentNode!==row||sheenSeen!==lastRefresh||!sheenBox){   /* a new card, or the list was rebuilt: measure once */
    if(sheen.parentNode!==row){sheen.classList.remove('on');row.appendChild(sheen);}
    var r=row.getBoundingClientRect();sheenBox={left:r.left,top:r.top+window.scrollY};sheenSeen=lastRefresh;}
  sheenX=ev.clientX-sheenBox.left;sheenY=ev.clientY+window.scrollY-sheenBox.top;
  if(!sheenRaf)sheenRaf=requestAnimationFrame(function(){sheenPaint();if(sheen)sheen.classList.add('on');});},{passive:true});
wrap.addEventListener('pointerleave',sheenOff);
"""
