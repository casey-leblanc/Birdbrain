"""Moving cards by hand: the list page's drag and drop, and the same from the keyboard.

Built on pointer events (mouse, touch and pen), not the browser's own drag-and-drop, so the card can feel like a
thing: it picks up after a few pixels, lifts, follows the pointer with a little weight, and the cards around it part
to show exactly where it will land. Letting go springs it into place; Esc, or letting go nowhere, springs it back.
A dock appears at the bottom of the window while a card is carried: drop on it for Completed or Archived.

Where a card may go is the app's decision (planner.py): the page asks, and a refusal comes back as one line, which
the card answers with a small shake before going home.

Nothing is measured while the card is merely following the pointer. Positions are read once at pick-up, and again
only when the card's landing place changes (a few times in a drag, never per frame); every one of those reads goes
through box(), which counts them so a test can hold the page to this.

From the keyboard, on a focused card: M picks it up, the arrow keys move it (between days and columns too), Enter
drops it, Esc puts it back; D sends it to Completed. Each move is said for screen readers ("Thursday, second of
four").

CSS and JS are included in the list page by report.py; the script runs inside the page's own closure (it uses its
api(), toast(), refreshBoard(), wrap, root, CALM, MS and EASE).
"""

CSS = """
/* moving cards (dragdrop.py) */
.row{touch-action:pan-y}
.row a.t{-webkit-user-drag:none}
:root.moving-card{-webkit-user-select:none;user-select:none}
:root.moving-card .grp.empty{display:block;opacity:.55}
:root.moving-card ul.day.empty{display:block;min-height:30px;margin:4px 0 12px;border-radius:8px;
 outline:1px dashed color-mix(in srgb,currentColor 30%,transparent);outline-offset:-1px}
.row.placeholder{outline:1px dashed color-mix(in srgb,currentColor 38%,transparent);outline-offset:-1px;border-radius:8px;background:none!important;box-shadow:none!important}
.row.placeholder>*{visibility:hidden}
.fly.dragging{z-index:60;will-change:transform}
.fly.dragging .row{transform:scale(1.03);transition:transform var(--m-fast) var(--m-out);box-shadow:0 22px 44px -12px rgba(0,0,0,.5),0 4px 10px -2px rgba(0,0,0,.25)}
.fly.dragging.wary .row{transform:scale(.99);opacity:.82}
.fly.dragging.shake .row{animation:refuse var(--m-slow) var(--m-move)}
@keyframes refuse{20%{transform:translateX(-8px)}40%{transform:translateX(7px)}60%{transform:translateX(-4px)}80%{transform:translateX(2px)}}
.row.carried{outline:2px solid var(--q-fg);outline-offset:2px;border-radius:8px;position:relative;z-index:2}
.dock{position:fixed;left:50%;bottom:22px;z-index:55;display:flex;gap:10px;padding:8px;border-radius:16px;background:var(--q-bg);
 border:1px solid var(--q-line);box-shadow:0 18px 44px rgba(0,0,0,.35);transform:translateX(-50%);animation:dock-in var(--m-base) var(--m-out)}
@keyframes dock-in{from{opacity:0;transform:translateX(-50%) translateY(14px)}}
.dock div{min-width:132px;padding:12px 18px;border-radius:10px;font-weight:700;text-align:center;color:var(--q-fg);background:var(--q-chip);
 transition:transform var(--m-fast) var(--m-out)}
.dock div.aimed{transform:scale(1.08);outline:2px solid var(--q-fg)}
:root.moving-card #toast{opacity:0}   /* the dock stands where the last message was; it's back when the card lands */
:root[data-layout=focus] .fly.dragging .row{transform:scale(1.015);box-shadow:0 12px 26px -12px rgba(0,0,0,.4)}
"""

JS = r"""
/* ---- Moving cards (dragdrop.py) ------------------------------------------------------------------------------ */
var drag=null,carry=null,scrollNow=window.scrollY,justDragged=false;
window.birdbrainMeasures=0;
window.addEventListener('scroll',function(){scrollNow=window.scrollY;},{passive:true});
function box(el){window.birdbrainMeasures++;return el.getBoundingClientRect();}   /* every layout read while a card is carried */
function say(t){document.getElementById('announce').textContent=t;}
function rowsOf(ul,skip){return [].slice.call(ul.children).filter(function(c){return c!==skip&&c.classList.contains('row')&&!c.hidden;});}
function dayLists(){return [].slice.call(wrap.querySelectorAll('.bands ul.day[data-day]')).filter(function(u){return !u.hidden;});}
function todayIso(){var d=new Date();return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2);}
function tooLate(li,day){   /* something from a site can't be planned for later than it's due (planner.py has the last word) */
  return !li.dataset.own&&!!li.dataset.deadline&&li.dataset.deadline>=todayIso()&&day>li.dataset.deadline;}
function undoMove(r,id){return function(){api('/api/move-undo',{undo:r.undo}).then(function(){return refreshBoard({id:id,part:'.tick'});})
  .then(function(){toast('Put back');}).catch(function(e){toast("Couldn't undo: "+e.message);});};}

/* where everything is, in page coordinates: read at pick-up and again only when the landing place changes */
function measure(d){var s=scrollNow,seen={};
  d.lists=dayLists().map(function(ul){var r=box(ul),h=ul.previousElementSibling,top=h&&h.classList.contains('grp')?box(h).top:r.top;
    return {ul:ul,day:ul.dataset.day,left:r.left,right:r.right,top:top+s,bottom:r.bottom+s,
      rows:rowsOf(ul,d.li).map(function(c){var b=box(c);seen[c.dataset.id]={x:b.left,y:b.top+s};return {el:c,mid:b.top+b.height/2+s};})};});
  var was=d.seen||{};d.seen=seen;return was;}
/* the cards that moved slide from where they were to where they are (FLIP): transform only */
function glideFrom(was,d){if(CALM.matches)return;Object.keys(d.seen).forEach(function(id){var a=was[id],b=d.seen[id];
  if(!a||(Math.abs(a.x-b.x)<1&&Math.abs(a.y-b.y)<1))return;var el=inList(id);
  if(el)el.animate([{transform:'translate('+(a.x-b.x)+'px,'+(a.y-b.y)+'px)'},{transform:'none'}],{duration:MS.base,easing:EASE.move});});}
function aimAt(d,x,y){var i,k=d.dock;
  for(i=0;i<k.length;i++)if(x>=k[i].left&&x<=k[i].right&&y>=k[i].top&&y<=k[i].bottom)return {bin:k[i].kind,el:k[i].el};
  var py=y+scrollNow,best=null;
  d.lists.forEach(function(l){if(x<l.left-16||x>l.right+16)return;var gap=py<l.top?l.top-py:py>l.bottom?py-l.bottom:0;
    if(gap<=56&&(!best||gap<best.gap))best={l:l,gap:gap};});
  if(!best)return null;var rows=best.l.rows,n=0;while(n<rows.length&&py>rows[n].mid)n++;
  return {list:best.l,index:n,before:rows[n]?rows[n].el:null};}
function sameAim(a,b){if(!a||!b)return a===b;return a.bin===b.bin&&(a.list&&a.list.ul)===(b.list&&b.list.ul)&&a.index===b.index;}
function setAim(d,t){d.aim=t;d.dock.forEach(function(k){k.el.classList.toggle('aimed',!!t&&t.bin===k.kind);});
  d.wary=!!(t&&t.list&&tooLate(d.li,t.list.day));d.g.f.classList.toggle('wary',d.wary);
  if(!t||!t.list||d.wary)return;                       /* over the dock, nowhere, or somewhere it can't go: no gap opens */
  t.list.ul.insertBefore(d.li,t.before);glideFrom(measure(d),d);}
function frame(){if(!drag||!drag.active)return;var d=drag;d.raf=0;
  var tx=d.x-d.grabX,ty=d.y-d.grabY,pull=CALM.matches?1:.34;   /* a little weight: it catches up over a few frames */
  d.gx+=(tx-d.gx)*pull;d.gy+=(ty-d.gy)*pull;
  var lean=root.dataset.layout==='glass'?3:1.2,tilt=CALM.matches?0:Math.max(-lean,Math.min(lean,(tx-d.gx)*.07));   /* Focus leans less */
  d.g.f.style.transform='translate3d('+(d.gx-d.g.r.left)+'px,'+(d.gy-d.g.r.top)+'px,0) rotate('+tilt+'deg)';
  var t=aimAt(d,d.x,d.y);if(!sameAim(t,d.aim))setAim(d,t);
  var edge=d.y<56?-1:d.y>window.innerHeight-56?1:0;if(edge)window.scrollBy(0,edge*14);   /* held near an edge: the list scrolls */
  if(edge||Math.abs(tx-d.gx)>.4||Math.abs(ty-d.gy)>.4)d.raf=requestAnimationFrame(frame);}
function pickUp(d){d.active=true;d.home={ul:d.li.parentNode,next:d.li.nextElementSibling};closeMenu(false);
  document.getAnimations().forEach(function(a){var t=a.effect&&a.effect.target;   /* cards still gliding from the last change arrive now, */
    if(t&&t.closest&&t.closest('.bands'))try{a.finish();}catch(e){}});              /* so what's measured is where they really are */
  var r=box(d.li);d.g=ghost(d.li);d.g.f.className='fly dragging';d.grabX=d.x0-r.left;d.grabY=d.y0-r.top;d.gx=r.left;d.gy=r.top;
  d.li.classList.add('placeholder');
  var before={};wrap.querySelectorAll('.bands .row[data-id]').forEach(function(c){var b=box(c);before[c.dataset.id]={x:b.left,y:b.top+scrollNow};});
  root.classList.add('moving-card');                    /* empty days come out as places to drop */
  var dock=document.createElement('div');dock.className='dock';dock.setAttribute('aria-hidden','true');
  dock.innerHTML='<div data-bin="completed">Completed</div><div data-bin="archived">Archived</div>';document.body.appendChild(dock);
  d.dockEl=dock;d.dock=[].slice.call(dock.children).map(function(el){var b=box(el);return {kind:el.dataset.bin,el:el,left:b.left-8,right:b.right+8,top:b.top-8,bottom:b.bottom+30};});
  d.seen=before;glideFrom(measure(d),d);d.aim=aimAt(d,d.x,d.y);}
function letGo(d){drag=null;if(d.raf)cancelAnimationFrame(d.raf);if(d.hold)clearTimeout(d.hold);}
function tidy(d){d.g.f.remove();d.dockEl.remove();d.li.classList.remove('placeholder');root.classList.remove('moving-card');}
function flyTo(d,x,y,scale,fade){var f=d.g.f;if(CALM.matches)return Promise.resolve();
  return f.animate([{transform:f.style.transform||'none',opacity:1},
    {transform:'translate3d('+(x-d.g.r.left)+'px,'+(y-d.g.r.top)+'px,0) scale('+(scale||1)+')',opacity:fade?0:1}],
    {duration:fade?MS.slow:MS.spring,easing:fade?EASE['in']:EASE.spring,fill:'forwards'}).finished.catch(function(){});}
function goHome(d,why){var was=measure(d);d.home.ul.insertBefore(d.li,d.home.next);glideFrom(was,(measure(d),d));
  var r=box(d.li),shake=Promise.resolve();
  if(why&&!CALM.matches){d.g.f.classList.remove('wary');d.g.f.classList.add('shake');shake=new Promise(function(ok){setTimeout(ok,MS.slow);});}
  if(why)toast(why);
  return shake.then(function(){return flyTo(d,r.left,r.top);}).then(function(){tidy(d);});}
function endDrag(cancel){var d=drag;if(!d)return;letGo(d);if(!d.active)return;
  justDragged=true;setTimeout(function(){justDragged=false;},60);
  var t=d.aim,id=d.id;
  if(cancel||!t)return goHome(d);
  if(t.list&&d.wary)return goHome(d,"It's due before then, so it can't be planned for later than its deadline.");
  if(t.bin){var b=box(t.el);
    return api('/api/move',{id:id,to:t.bin}).then(function(r){return flyTo(d,b.left+b.width/2-d.g.r.width/2,b.top,.5,true).then(function(){
      tidy(d);return refreshBoard();}).then(function(){pulseBin(t.bin);toast(r.says,undoMove(r,id));say(r.says);});})
    .catch(function(e){return goHome(d,e.message);});}
  var next=d.li.nextElementSibling;while(next&&!next.classList.contains('row'))next=next.nextElementSibling;
  if(d.li.parentNode===d.home.ul&&d.li.nextElementSibling===d.home.next)return goHome(d);   /* let go where it was */
  return api('/api/move',{id:id,to:'day',day:t.list.day,before:next?next.dataset.id:null}).then(function(r){
    var spot=box(d.li);return flyTo(d,spot.left,spot.top).then(function(){tidy(d);return refreshBoard({id:id,part:'.tick'});})
      .then(function(){landedAt(spot.left+spot.width/2,spot.top+spot.height/2);toast(r.says,undoMove(r,id));say(r.heard);});})
  .catch(function(e){return goHome(d,e.message);});}
function landedAt(x,y){if(typeof rippleAt==='function')rippleAt(x,y);}
wrap.addEventListener('pointerdown',function(ev){
  if(!LIVE||drag||carry||(ev.pointerType==='mouse'&&ev.button!==0))return;
  var li=ev.target.closest('.row[data-id]');
  if(!li||ev.target.closest('button,input,label,summary,.lab,.code'))return;
  drag={li:li,id:li.dataset.id,x0:ev.clientX,y0:ev.clientY,x:ev.clientX,y:ev.clientY,pid:ev.pointerId,active:false,touch:ev.pointerType==='touch'};
  if(drag.touch){var d=drag;d.hold=setTimeout(function(){if(drag===d&&!d.active){pickUp(d);if(navigator.vibrate)navigator.vibrate(8);}},380);}});
window.addEventListener('pointermove',function(ev){var d=drag;if(!d||ev.pointerId!==d.pid)return;
  d.x=ev.clientX;d.y=ev.clientY;
  if(!d.active){var far=Math.abs(d.x-d.x0)+Math.abs(d.y-d.y0);
    if(d.touch){if(far>10)letGo(d);return;}             /* a finger that moves before the hold is scrolling */
    if(far<5)return;pickUp(d);}
  if(!d.raf)d.raf=requestAnimationFrame(frame);},{passive:true});
window.addEventListener('pointerup',function(ev){if(drag&&ev.pointerId===drag.pid)endDrag(false);});
window.addEventListener('pointercancel',function(ev){if(drag&&ev.pointerId===drag.pid)endDrag(true);});
document.addEventListener('touchmove',function(ev){if(drag&&drag.active)ev.preventDefault();},{passive:false});
document.addEventListener('dragstart',function(ev){if(ev.target.closest&&ev.target.closest('.row'))ev.preventDefault();});
window.addEventListener('click',function(ev){if(justDragged){ev.preventDefault();ev.stopPropagation();justDragged=false;}},true);
document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&drag&&drag.active){ev.preventDefault();ev.stopPropagation();endDrag(true);}},true);

/* ---- The same from the keyboard: M picks up, arrows move, Enter drops, Esc puts back; D sends to Completed ---- */
var NTH=['first','second','third','fourth','fifth','sixth','seventh','eighth','ninth','tenth'],
  COUNT=['one','two','three','four','five','six','seven','eight','nine','ten'];
function whereIs(li){var ul=li.parentNode,h=ul.previousElementSibling,rows=rowsOf(ul),n=rows.indexOf(li)+1,name=h&&h.classList.contains('grp')?h.textContent.trim():'the list';
  return name.charAt(0).toUpperCase()+name.slice(1)+', '+(NTH[n-1]||'number '+n)+' of '+(COUNT[rows.length-1]||rows.length);}
function shift(li,ul,before){var was={};wrap.querySelectorAll('.bands .row[data-id]').forEach(function(c){var b=box(c);was[c.dataset.id]={x:b.left,y:b.top};});
  ul.insertBefore(li,before);
  if(!CALM.matches)wrap.querySelectorAll('.bands .row[data-id]').forEach(function(c){var a=was[c.dataset.id],b=box(c);
    if(a&&(Math.abs(a.x-b.left)>1||Math.abs(a.y-b.top)>1))c.animate([{transform:'translate('+(a.x-b.left)+'px,'+(a.y-b.top)+'px)'},{transform:'none'}],
      {duration:MS.base,easing:EASE.move});});
  var t=li.querySelector('.tick');if(t)t.focus({preventScroll:true});li.scrollIntoView({block:'nearest'});}
function pickUpKey(li){carry={li:li,id:li.dataset.id,home:{ul:li.parentNode,next:li.nextElementSibling}};
  root.classList.add('moving-card');li.classList.add('carried');
  say('Picked up. '+whereIs(li)+'. Arrow keys move it, Enter drops it, Escape puts it back.');}
function stepKey(key){var li=carry.li,ul=li.parentNode,lists=dayLists(),i=lists.indexOf(ul),rows=rowsOf(ul),n=rows.indexOf(li),to=null;
  if(key==='ArrowDown'){if(i>=0&&n<rows.length-1)to=[ul,rows[n+1].nextElementSibling];else if(lists[i+1])to=[lists[i+1],lists[i+1].firstElementChild];}
  else if(key==='ArrowUp'){if(i>=0&&n>0)to=[ul,rows[n-1]];else if(i>0)to=[lists[i-1],null];else if(i<0&&lists.length)to=[lists[0],lists[0].firstElementChild];}
  else{var bands=[].slice.call(wrap.querySelectorAll('.band')),b=bands.indexOf(ul.closest('.band'))+(key==='ArrowRight'?1:-1),
      side=bands[b]&&bands[b].querySelector('ul.day[data-day]');if(side)to=[side,side.firstElementChild];}
  if(!to){say('It can\'t go further that way.');return;}
  if(tooLate(li,to[0].dataset.day)){say('It\'s due before then, so it can\'t be planned for later than its deadline.');return;}
  shift(li,to[0],to[1]);say(whereIs(li));}
function endKey(drop){var c=carry;if(!c)return;carry=null;
  var done=function(){c.li.classList.remove('carried');root.classList.remove('moving-card');},
    home=function(why){shift(c.li,c.home.ul,c.home.next);done();var t=c.li.querySelector('.tick');if(t)t.focus();say(why||'Put back.');if(why)toast(why);};
  if(!drop||!c.li.parentNode.dataset.day||(c.li.parentNode===c.home.ul&&c.li.nextElementSibling===c.home.next))return home();
  var next=c.li.nextElementSibling;while(next&&!next.classList.contains('row'))next=next.nextElementSibling;
  api('/api/move',{id:c.id,to:'day',day:c.li.parentNode.dataset.day,before:next?next.dataset.id:null}).then(function(r){
    done();return refreshBoard({id:c.id,part:'.tick'}).then(function(){toast(r.says,undoMove(r,c.id));say(r.heard);
      var row=inList(c.id);if(row){var b=box(row);landedAt(b.left+b.width/2,b.top+b.height/2);}});})
  .catch(function(e){home(e.message);});}
wrap.addEventListener('keydown',function(ev){
  if(ev.ctrlKey||ev.metaKey||ev.altKey||!LIVE)return;
  var row=ev.target.closest&&ev.target.closest('.bands .row[data-id]'),k=ev.key;
  if(carry){   /* carrying: only these keys mean anything */
    if(k==='Enter')endKey(true);else if(k==='Escape')endKey(false);
    else if(k==='ArrowDown'||k==='ArrowUp'||k==='ArrowLeft'||k==='ArrowRight')stepKey(k);else if(k==='Tab')endKey(false);else return;
    ev.preventDefault();ev.stopPropagation();return;}
  if(!row||(ev.target.tagName==='INPUT'&&ev.target.type!=='checkbox'))return;
  if(k==='m'||k==='M'){ev.preventDefault();ev.stopPropagation();pickUpKey(row);}
  else if(k==='d'||k==='D'){ev.preventDefault();ev.stopPropagation();var id=row.dataset.id,nx=neighbour(row);
    api('/api/move',{id:id,to:'completed'}).then(function(r){return refreshBoard({id:nx,part:'.tick'}).then(function(){
      pulseBin('completed');toast(r.says,undoMove(r,id));say(r.says);});}).catch(function(e){toast(e.message);});}
},true);
"""
