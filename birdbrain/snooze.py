"""Snooze: put a card out of sight until a day. It comes back by itself, and says it was snoozed.

    S on a card  ->  until tomorrow, next week, or a day you pick

A card never stays hidden past its deadline. Ask for a day after it's due and it comes back the day it's due
instead, and both the choice and the confirmation say so. Something due today can't be snoozed at all. Work that
is already overdue can be snoozed to any day: there is no deadline left to miss.

While it sleeps a card waits in Archived ("Snoozed until Friday", with Wake it now). The day it comes back it sits
in its usual place with a "back from snooze" tag for that day.

The rules are here; CSS and JS for the list page are below them (included by report.py, run in the page's closure).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from store import Item, Store


class Refused(ValueError):
    """A snooze that can't be made, with the one line that says why."""


def asleep(item: Item, today: date) -> bool:
    return bool(item.snoozed and item.snoozed > today)


def back_today(item: Item, today: date) -> bool:
    return item.snoozed == today


def say_day(day: date, today: date) -> str:
    n = (day - today).days
    return "tomorrow" if n == 1 else f"{day:%A}" if n < 7 else f"{day:%A}, {day:%b} {day.day}"


def comes_back(item: Item, asked: date, now: datetime) -> date:
    """The day a card snoozed until `asked` really returns: no later than the day it's due (unless that has passed)."""
    due = item.due.date()
    return due if item.due >= now and now.date() <= due < asked else asked


def choices(item: Item, now: datetime) -> list[dict]:
    """What the snooze window offers for this card: tomorrow and next week (Monday), each with the day it would
    really come back and a note if that isn't the day asked for."""
    today = now.date()
    monday = today + timedelta(days=(7 - today.weekday()) or 7)
    if monday == today + timedelta(days=1):       # on a Sunday, "next week" is the Monday after tomorrow's
        monday += timedelta(days=7)
    out = []
    for key, label, asked in (("tomorrow", "Tomorrow", today + timedelta(days=1)), ("week", "Next week", monday)):
        day = comes_back(item, asked, now)
        note = "" if day == asked else f"it's due {say_day(day, today)}, so it comes back then"
        out.append({"key": key, "label": label, "day": day.isoformat(), "ask": asked.isoformat(), "says": say_day(asked, today).capitalize()
                    if key == "week" else "", "note": note})
    return out


def snooze(store: Store, item_id: str, until: date | None, now: datetime | None = None) -> dict:
    """Hide a card until `until` (None wakes it now). Says what happened in one line, and gives back what it was
    before, for Undo."""
    now = now or datetime.now()
    today = now.date()
    item = store.get(item_id)
    if not item:
        raise Refused("That card isn't on your list any more.")
    if until is None:
        was = store.snooze(item_id, None)
        return {"ok": True, "until": None, "was": was.isoformat() if was else None, "says": "Back on your list"}
    if item.done_at:
        raise Refused("It's already done.")
    if until <= today:
        raise Refused("Pick a day after today.")
    if item.due.date() == today and item.due >= now:
        raise Refused("It's due today, so it can't be snoozed.")
    day = comes_back(item, until, now)
    was = store.snooze(item_id, day)
    says = f"Snoozed until {say_day(day, today)}"
    if day != until:
        says += f": it's due then, so it can't sleep until {say_day(until, today)}"
    return {"ok": True, "until": day.isoformat(), "was": was.isoformat() if was else None, "says": says}


CSS = """
/* snooze (snooze.py). On a card the Snooze button waits out of sight with Archive, until the card is pointed at. */
.act.snooze{margin-left:auto;opacity:0;transition:opacity var(--m-fast) var(--m-out)}
.act.snooze+.act.arch{margin-left:0}
.row:hover .act.snooze,.row:focus-within .act.snooze{opacity:1}
@media (hover:none){.act.snooze{opacity:1}}
#snooze .quick-hint{padding:4px 20px 14px}
#snooze .snz-pick input{font:inherit;color:inherit;background:var(--q-chip);border:1px solid var(--q-line);border-radius:8px;padding:8px 10px}
:root[data-mode=dark] #snooze .snz-pick input{color-scheme:dark}
#snooze .snz-title{margin:18px 20px 4px;font-weight:600}
#snooze .snz-list{list-style:none;margin:0;padding:6px 8px}
#snooze .snz-list button{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;width:100%;padding:10px 12px;border:0;border-radius:8px;
 background:none;color:inherit;font:inherit;text-align:left;cursor:pointer}
#snooze .snz-list button:hover,#snooze .snz-list button:focus-visible{background:var(--q-chip);outline:none}
#snooze .snz-list kbd{font:inherit;font-size:.8125rem;color:var(--q-muted);border:1px solid var(--q-line);border-radius:4px;padding:0 5px;margin-left:auto}
#snooze .snz-list small{font-size:.8125rem;color:var(--q-muted)}
#snooze .snz-pick{display:flex;align-items:center;gap:10px;padding:4px 20px 6px}
#snooze .snz-pick input{flex:1;min-width:0}
#snooze .form-error{margin:0 20px 8px}
.snz{font-size:.75rem;font-weight:600;padding:1px 7px;border-radius:999px;border:1px solid var(--q-line)}
"""

JS = r"""
/* ---- Snooze (snooze.py): S on a card, or its Snooze button --------------------------------------------------- */
var snzDlg=document.getElementById('snooze'),snzList=document.getElementById('snz-list'),snzDay=document.getElementById('snz-day'),
  snzErr=document.getElementById('snz-error'),snzId=null,snzNext=null;
function snoozeUndo(r,id){return function(){api('/api/snooze',{id:id,until:r.was}).then(function(){return refreshBoard({id:id,part:'.tick'});})
  .then(function(){toast(r.until?'Back on your list':'Snoozed again');}).catch(function(e){toast("Couldn't undo: "+e.message);});};}
function snoozeTo(day){var id=snzId,next=snzNext;snzErr.textContent='';
  api('/api/snooze',{id:id,until:day}).then(function(r){snzDlg.close();
    return refreshBoard({id:next,part:'.tick'}).then(function(){pulseBin('archived');toast(r.says,snoozeUndo(r,id));say(r.says);});})
  .catch(function(e){snzErr.textContent=e.message;});}
function openSnooze(row){if(!LIVE||!row||document.querySelector('dialog[open]'))return;
  snzId=row.dataset.id;snzNext=neighbour(row);snzErr.textContent='';snzDay.value='';
  api('/api/snooze',{id:snzId,ask:true}).then(function(r){
    document.getElementById('snz-title').textContent='Snooze “'+titleOf(row)+'” until';
    snzList.textContent='';r.choices.forEach(function(c,i){var li=document.createElement('li'),b=document.createElement('button'),n=document.createElement('span');
      b.type='button';b.dataset.day=c.ask;n.textContent=c.label+(c.says?' ('+c.says+')':'');b.appendChild(n);
      if(c.note){var s=document.createElement('small');s.textContent=c.note;b.appendChild(s);}
      var k=document.createElement('kbd');k.textContent=c.key==='tomorrow'?'T':'W';b.appendChild(k);
      b.addEventListener('click',function(){snoozeTo(c.ask);});   /* the app brings it back sooner if it's due sooner, and says so */li.appendChild(b);snzList.appendChild(li);});
    snzDay.min=r.min;snzDlg.showModal();snzList.querySelector('button').focus();})
  .catch(function(e){toast(e.message);});}
snzDlg.addEventListener('keydown',function(ev){if(ev.target===snzDay||ev.ctrlKey||ev.metaKey||ev.altKey)return;var k=ev.key.toLowerCase(),b=snzList.querySelectorAll('button');
  if(k==='t'&&b[0]){ev.preventDefault();b[0].click();}else if(k==='w'&&b[1]){ev.preventDefault();b[1].click();}
  else if(k==='p'){ev.preventDefault();snzDay.focus();}
  else if(k==='arrowdown'||k==='arrowup'){ev.preventDefault();var all=[].slice.call(b).concat([snzDay]),i=all.indexOf(document.activeElement);
    all[(i+(k==='arrowdown'?1:all.length-1))%all.length].focus();}});
document.getElementById('snz-form').addEventListener('submit',function(ev){ev.preventDefault();
  if(!snzDay.value){snzErr.textContent='Pick a day first.';return;}snoozeTo(snzDay.value);});
snzDay.addEventListener('keydown',function(ev){if(ev.key==='Enter'){ev.preventDefault();document.getElementById('snz-form').requestSubmit();}});
snzDlg.addEventListener('click',function(ev){if(ev.target===snzDlg)snzDlg.close();});
wrap.addEventListener('keydown',function(ev){   /* S on a card snoozes it (anywhere else S is Settings) */
  if(ev.ctrlKey||ev.metaKey||ev.altKey||!LIVE||carry||(ev.key!=='s'&&ev.key!=='S'))return;
  var row=ev.target.closest&&ev.target.closest('.bands .row[data-id]');
  if(!row||(ev.target.tagName==='INPUT'&&ev.target.type!=='checkbox'))return;
  ev.preventDefault();ev.stopPropagation();openSnooze(row);},true);
on('click','.act.snooze',function(btn){openSnooze(btn.closest('.row'));});
on('click','.act.wake',function(btn){var row=btn.closest('.row'),id=row.dataset.id;
  api('/api/snooze',{id:id,until:null}).then(function(r){return refreshBoard({id:id,part:'.tick'}).then(function(){toast(r.says,snoozeUndo(r,id));});})
  .catch(function(e){toast(e.message);});});
"""


def dialog() -> str:
    return ('<dialog id="snooze" class="quick" aria-labelledby="snz-title"><p class="snz-title" id="snz-title"></p>'
            '<ul class="snz-list" id="snz-list"></ul>'
            '<form class="snz-pick" id="snz-form" novalidate><label class="sr" for="snz-day">Or pick a day</label>'
            '<input type="date" id="snz-day"><button type="submit" class="btn">Snooze</button></form>'
            '<p class="form-error" id="snz-error" role="alert"></p>'
            '<p class="quick-hint"><kbd>T</kbd> tomorrow<span> · </span><kbd>W</kbd> next week<span> · </span>'
            '<kbd>P</kbd> pick a day<span> · </span><kbd>Esc</kbd> cancel</p></dialog>')
