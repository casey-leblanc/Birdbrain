"""Search and commands: one line, opened by Ctrl+K or "/" (and by # or @, which start it off for a label or class).

Typing narrows the list behind it as you go: a word, #label or @class. The same line also runs things: type "scan",
"settings", "new label", "night"… and the matching commands are listed under it. Arrow keys choose, Enter runs the
chosen one, and with none chosen Enter just keeps the list narrowed. Esc closes and shows everything again.

A command is chosen for you only when what you typed starts its name or one of its other words ("sc" is Scan now),
so a word that merely appears in a command's name still filters the list unless you arrow down to the command.

COMMANDS is the whole menu: (id, name, other words it answers to, the key that also does it). What each one does is
in JS below, by id. CSS and JS are included in the list page by report.py; the script runs in the page's closure.
"""

COMMANDS = (
    ("scan", "Scan now", "refresh check sync update list", "R"),
    ("quick", "Quick write", "add new item write", "Space"),
    ("add", "Add with the full form", "new item form", "N"),
    ("settings", "Settings", "preferences options", "S"),
    ("label", "New label", "tag labels", ""),
    ("night", "Night", "dark mode", ""),
    ("day", "Day", "light mode", ""),
    ("glass", "Glass layout", "look frosted photo", ""),
    ("focus", "Focus layout", "look plain calm", ""),
    ("everything", "Show everything", "everything clear filter all", "Esc"),
    ("completed", "Show Completed", "completed done finished ticked", ""),
    ("archived", "Show Archived", "archived hidden snoozed", ""),
    ("notifications", "Notifications", "notify reminders morning evening sounds", ""),
    ("signin", "Sign in to your school sites", "login log moodle outlook", ""),
    ("keys", "Show the keys", "keys shortcuts keyboard help", "?"),
    ("updates", "Check for updates", "updates version build", ""),
    ("telegram", "Set up your phone (Telegram)", "telegram phone bot", ""),
    ("backup", "Back up or move your own items", "export import backup file computer", ""),
    ("problem", "Report a problem", "bug help broken wrong support log", ""),
    ("quit", "Quit Birdbrain", "exit close stop", ""),
)


def data() -> list[dict]:
    """For the page: each command with the words it answers to, lowercased."""
    return [{"id": i, "name": name, "words": [name.lower(), *more.split()], "key": key} for i, name, more, key in COMMANDS]


CSS = """
/* search and commands (commands.py) */
.cmds{list-style:none;margin:0;padding:0 8px;max-height:min(46vh,340px);overflow-y:auto}
.cmds:empty{display:none}
.cmds li{display:flex;justify-content:space-between;align-items:baseline;gap:16px;padding:8px 12px;border-radius:8px;cursor:pointer}
.cmds li[aria-selected=true]{background:var(--q-chip)}
.cmds li kbd{font:inherit;font-size:.8125rem;color:var(--q-muted);border:1px solid var(--q-line);border-radius:4px;padding:0 5px}
.cmds-title{margin:6px 20px 2px;font-size:.75rem;font-weight:600;color:var(--q-muted)}
"""

JS = r"""
/* ---- Search and commands (commands.py) ----------------------------------------------------------------------- */
var cmdList=document.getElementById('cmd-list'),cmdHint=document.getElementById('filter-hint'),cmdShown=[],cmdAt=-1;
var CMD_DO={scan:function(){scanNow();},quick:function(){openQuick();},add:function(){openItemForm(null,null);},
  settings:function(){openSettings();},
  label:function(){openSettings('labels');var b=document.getElementById('label-new');if(b)b.focus();},
  night:function(){PREFS.mode='dark';applyTheme();savePrefs({mode:'dark'});toast('Night');},
  day:function(){PREFS.mode='light';applyTheme();savePrefs({mode:'light'});toast('Day');},
  glass:function(){pickLayout('glass');},focus:function(){pickLayout('focus');},
  everything:function(){setFilter(null);},
  completed:function(){showBin('completed');},archived:function(){showBin('archived');},
  notifications:function(){openSettings('notifications');},
  signin:function(){api('/api/sign-in').then(function(){toast("The sign-in window is opening. It closes by itself once you're signed in.");}).catch(function(e){toast(e.message);});},
  keys:function(){openKeys();},updates:function(){MENU_DO.update();},
  telegram:function(){openSettings('advanced','fold-telegram');},problem:function(){openProblem();},backup:function(){openSettings('advanced','fold-backup');},quit:function(){quitNow();}};
function pickLayout(to){if(PREFS.layout===to){toast('Already in '+(to==='glass'?'Glass':'Focus'));return;}
  var r=settings.querySelector('input[name=layout][value='+to+']');if(r)r.click();}
function showBin(kind){var bin=wrap.querySelector('.bin.'+kind);if(!bin){toast('Nothing there yet');return;}
  bin.open=true;bin.scrollIntoView({block:'start'});var first=bin.querySelector('.row .tick,summary');if(first)first.focus({preventScroll:true});}
/* which commands answer to what's typed, best first; `sure` when it starts a command's name or one of its words */
function cmdMatches(text){var q=text.trim().toLowerCase();if(q.charAt(0)==='#'||q.charAt(0)==='@')return {list:[],sure:false};
  if(!q)return {list:DATA.commands.slice(),sure:false};
  var starts=[],has=[];DATA.commands.forEach(function(c){
    if(c.words.some(function(w){return w.indexOf(q)===0;}))starts.push(c);
    else if(c.words.some(function(w){return w.indexOf(q)>=0;}))has.push(c);});
  return {list:starts.concat(has),sure:starts.length>0&&q.length>1};}
function cmdPaint(){cmdList.textContent='';cmdShown.forEach(function(c,i){var li=document.createElement('li'),n=document.createElement('span');
    li.id='cmd-'+c.id;li.setAttribute('role','option');li.setAttribute('aria-selected',i===cmdAt?'true':'false');n.textContent=c.name;li.appendChild(n);
    if(c.key){var k=document.createElement('kbd');k.textContent=c.key;li.appendChild(k);}
    li.addEventListener('mousemove',function(){if(cmdAt!==i){cmdAt=i;cmdMark();}});
    li.addEventListener('click',function(){cmdAt=i;cmdRun();});cmdList.appendChild(li);});
  cmdMark();}
function cmdMark(){[].forEach.call(cmdList.children,function(li,i){li.setAttribute('aria-selected',i===cmdAt?'true':'false');
    if(i===cmdAt)li.scrollIntoView({block:'nearest'});});
  fLine.setAttribute('aria-activedescendant',cmdAt>=0&&cmdShown[cmdAt]?'cmd-'+cmdShown[cmdAt].id:'');
  cmdHint.innerHTML=cmdAt>=0?'<kbd>Enter</kbd> '+cmdShown[cmdAt].name.toLowerCase()+'<span> · </span><kbd>↑</kbd><kbd>↓</kbd> choose<span> · </span><kbd>Esc</kbd> close'
    :(FILTER?'<kbd>Enter</kbd> keep it<span> · </span>':'')+(cmdShown.length?'<kbd>↓</kbd> commands<span> · </span>':'')+'<kbd>Esc</kbd> show everything';}
function cmdRead(){var m=cmdMatches(fLine.value);cmdShown=m.list;cmdAt=m.sure?0:-1;cmdPaint();
  /* a line that is plainly a command doesn't also hide the whole list behind it */
  if(m.sure&&FILTER&&FILTER.what==='text'){setFilter(null);fSays.textContent='';}}
/* Enter: the chosen command, if one is. Says whether it ran one. */
function cmdRun(){var c=cmdShown[cmdAt];if(!c)return false;
  setFilter(null);filterDlg.close();setTimeout(function(){CMD_DO[c.id]();},0);return true;}
fLine.addEventListener('input',cmdRead);
fLine.addEventListener('keydown',function(ev){var k=ev.key;
  if(k==='ArrowDown'||k==='ArrowUp'){ev.preventDefault();if(!cmdShown.length)return;
    cmdAt=k==='ArrowDown'?Math.min(cmdShown.length-1,cmdAt+1):Math.max(-1,cmdAt-1);cmdMark();}});
document.addEventListener('keydown',function(ev){   /* Ctrl+K (Cmd+K on a Mac) from anywhere on the list */
  if((ev.ctrlKey||ev.metaKey)&&!ev.altKey&&!ev.shiftKey&&(ev.key==='k'||ev.key==='K')){ev.preventDefault();openFilter('');}});
"""
