"""The Glass layout (the default), modelled on caseyleblanc.dev.

One frosted panel floats over the open sky and holds everything: a header row
(today, the title, the buttons), a slim strip naming the next exam and quiz,
then Now / This week / Later as three glass columns, laid out like the site's
blog (a wider middle column). Items sit clear on the column's glass and only
take a wash under the pointer. Headings are lowercase and dates italic, as on
the site; the font is Atkinson Hyperlegible.

Every theme is a colour scheme here (SCHEMES): its own photo for light mode
(day) and dark mode (night), a glass tint, a title colour and an exam-chip
colour. The photos are in assets/backgrounds, credited in CREDITS.txt there.

Urgency is carried by colour on the due date, the same in every scheme:
  overdue   a solid red chip on the date, and a faint red tint on the tile
  today     an amber chip on the date
  tomorrow  a yellow chip on the date
Each day's label carries a dot of the same colour. Exams get a solid chip in the scheme's exam colour and a bold title, quizzes an
outlined chip; that keeps "what it is" apart from "how soon" (the heat colours).

Text is white on tinted glass. Each scheme's glass is dark enough that every
text colour stays at or above 4.5:1 over the brightest part of its photo; chips
use dark ink on solid colour. report.py uses this stylesheet when the saved
layout is "glass".
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

BG_DIR = Path(__file__).parent / "assets" / "backgrounds"

# Per scheme: title colour, exam chip (and its ink), focus ring, then per mode the glass tint, the dialog
# tint and a fallback colour shown until the photo loads. High contrast also drops the see-through text.
# tb_* override the window buttons' colour, glow and fade where a photo is too bright for white ones.
SCHEMES = {
    "forest": dict(name="Forest", common=dict(title="rgba(255,255,255,.82)", lav="#DCD0FF", lav_ink="#21173F", focus="#FFFFFF"),
                   # a bright sky behind the title bar: dark window buttons on a pale fade
                   light=dict(glass="rgba(36,41,51,.76)", sheet="rgba(34,39,50,.92)", bg="#7FA3D2", tb_fg="#16212B",
                              tb_shadow="0 0 6px rgba(255,255,255,.8)",
                              tb_bg="linear-gradient(rgba(255,255,255,.4),rgba(255,255,255,.12) 70%,rgba(255,255,255,0))"),
                   dark=dict(glass="rgba(16,22,34,.64)", sheet="rgba(18,24,36,.92)", bg="#0A1230")),
    "birdbrain": dict(name="Birdbrain", common=dict(title="#DDD5FF", lav="#D9D0FF", lav_ink="#21173F", focus="#FFFFFF"),
                      light=dict(glass="rgba(42,34,74,.74)", sheet="rgba(36,30,64,.92)", bg="#9C8BC9"),
                      dark=dict(glass="rgba(26,20,50,.66)", sheet="rgba(24,20,46,.92)", bg="#2A2150")),
    # Cloudy: towering cumulus by day, a sea of clouds under the moon by night; pale white where Cozy was green.
    # The glass is a neutral cool slate, as dark as each photo's brightest clouds need (the Measured Glass Rule).
    "cloudy": dict(name="Cloudy", common=dict(title="#F2F5F9", lav="#EEF2F7", lav_ink="#1B2430", focus="#FFFFFF"),
                   light=dict(glass="rgba(32,40,54,.76)", sheet="rgba(29,36,49,.92)", bg="#5E7FA6"),
                   dark=dict(glass="rgba(18,26,42,.66)", sheet="rgba(16,23,38,.92)", bg="#12306A")),
    "contrast": dict(name="High contrast", common=dict(title="#FFFFFF", lav="#7FE0FF", lav_ink="#000000", focus="#FFE14D",
                                 t2="#FFFFFF", edge="#FFFFFF", line="rgba(255,255,255,.55)"),
                     light=dict(glass="rgba(0,0,0,.86)", sheet="rgba(0,0,0,.95)", bg="#BDBDBD"),
                     dark=dict(glass="rgba(0,0,0,.84)", sheet="rgba(0,0,0,.95)", bg="#1A1A1A")),
    "dusk": dict(name="Dusk", common=dict(title="#F8D6E0", lav="#A9DBF2", lav_ink="#0E2533", focus="#F5B38A"),
                 light=dict(glass="rgba(36,34,64,.72)", sheet="rgba(34,32,60,.92)", bg="#C98AA0"),
                 dark=dict(glass="rgba(14,26,40,.72)", sheet="rgba(16,24,38,.92)", bg="#1F4A5C")),
}


def photo_name(theme: str, mode: str, thumb: bool = False) -> str:
    return f"{theme}-{mode}" + ("-thumb" if thumb else "")


def photo_path(name: str) -> Path:
    """Where a photo lives: the bundled ones in assets/backgrounds, the student's own (custom-*) in
    Birdbrain's data folder, where custom.py puts them."""
    if name.startswith("custom-"):
        from config import DATA_DIR
        return DATA_DIR / "photos" / f"{name}.jpg"
    return BG_DIR / f"{name}.jpg"


def file_url(name: str) -> str | None:
    """A photo as a file:// address, for the read-only copy of the page."""
    path = photo_path(name)
    return path.as_uri() if path.exists() else None


def scheme_css(key: str, sc: dict, photo: Callable[[str], str | None], versions: dict | None = None) -> str:
    """The colour blocks for one scheme, day and night. `versions` ({mode: n}) makes a replaced photo's
    address change, so the browser fetches the new one."""
    blocks = []
    for mode in ("light", "dark"):
        v = {**sc["common"], **sc[mode]}
        url = photo(photo_name(key, mode))
        if url and versions and versions.get(mode):
            url += ("&" if "?" in url else "?") + f"v={versions[mode]}"
        v["photo"] = f'url("{url}")' if url else "none"
        props = ";".join(f"--{'' if k.startswith('tb_') else 'g-'}{k.replace('_', '-')}:{val}" for k, val in v.items())
        blocks.append(f":root[data-theme={key}][data-mode={mode}]{{{props}}}")
    return "".join(blocks)


def css(photo: Callable[[str], str | None]) -> str:
    """The stylesheet, with one block of colours and a photo address per scheme and mode.
    `photo(name)` gives the address of <name>.jpg, or None to show the fallback colour.
    The Custom scheme's blocks come separately (custom.css), so they can change while the page is open."""
    return BASE + "".join(scheme_css(key, sc, photo) for key, sc in SCHEMES.items()) + CSS


BASE = """
:root{--g-t1:rgba(255,255,255,.96);--g-t2:rgba(255,255,255,.88);--g-edge:rgba(255,255,255,.6);
--g-line:rgba(255,255,255,.2);--g-rule:rgba(255,255,255,.16);--g-glass:rgba(36,41,51,.76);--g-pane:rgba(255,255,255,.055);
--g-tile-hover:rgba(255,255,255,.085);--g-sheet:rgba(34,39,50,.92);
--g-red:#FF8577;--g-amber:#FFBC5C;--g-yellow:#FFE27D;--g-lav:#DCD0FF;--g-ink:#20140E;--g-lav-ink:#21173F;
--g-title:rgba(255,255,255,.82);--g-focus:#FFFFFF;--g-bg:#7FA3D2;--g-photo:none;color-scheme:dark;
--g-lift:0 6px 14px -6px rgba(0,0,0,.55),0 2px 4px -2px rgba(0,0,0,.3)}   /* hover only: a pressable surface rises */
"""

CSS = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:var(--g-bg);color:var(--g-t1);font:400 16px/1.5 "Birdbrain Sans","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body::before{content:"";position:fixed;inset:-10px;z-index:-1;background:var(--g-photo) center/cover no-repeat,var(--g-bg)}
body.static .needs-app{display:none!important}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
p,h1,h2,h3,ul{margin:0;padding:0}ul{list-style:none}
:focus-visible{outline:2px solid var(--g-focus);outline-offset:3px;border-radius:4px}

/* the frosted frame: one header row (today, title, actions), the status line, the next exam and quiz, three glass
   columns. Spacing runs on 8px; type on five sizes (13 / 16 / 20 / 28 / 40px). */
.wrap{width:min(1500px,calc(100% - 2 * max(16px,4vw)));margin:48px auto 64px;padding:32px;
 display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr) minmax(0,1fr);column-gap:24px;row-gap:24px;align-items:start;
 background:var(--g-glass);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);outline:2px solid var(--g-edge);border-radius:10px;
 box-shadow:inset 3px 3px 6px rgba(255,255,255,.4),inset -3px -3px 6px rgba(0,0,0,.4)}
:root[data-frame=narrow] .wrap{width:min(1240px,calc(100% - 2 * max(24px,10vw)))}   /* more of the photo shows */
.top{display:contents}
h1{grid-column:2;grid-row:1;justify-self:center;align-self:center;font-size:1.75rem;font-weight:700;line-height:1.1;letter-spacing:.01em;color:var(--g-title);text-transform:lowercase}
.status{grid-column:1/-1;grid-row:2;justify-self:center;text-align:center;max-width:60ch;margin-top:-16px;font-size:.8125rem;color:var(--g-t2)}
.status.problem{background:var(--g-red);color:var(--g-ink);font-weight:700;padding:2px 10px;border-radius:6px}
.status{--bar-track:rgba(255,255,255,.22);--bar-fill:rgba(255,255,255,.92)}
.actions{grid-column:3;grid-row:1;justify-self:end;align-self:center;display:flex;gap:8px}
.today{grid-column:1;grid-row:1;align-self:center;display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px}
/* next exam and next quiz: side by side, or one line across when alone */
.next{grid-column:1/-1;grid-row:3;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:24px}
/* the cadence between the page's parts: the summary strip sits 24px under the header, the list 32px under the
   strip, and the archive bins 48px under the list, so each step away from what's due now is a step further off.
   Columns hug their own items: a busy week doesn't stretch Now and Later into tall, empty panes. */
.bands{grid-column:1/-1;grid-row:4;display:grid;grid-template-columns:subgrid;row-gap:24px;align-items:start;margin-top:8px}
.bins{grid-column:1/-1;grid-row:5;margin-top:24px}

/* glass panels (the site's sidebar panels and blog entries): a faint wash and a hairline; only the frame is bevelled */
.nx,.band,.bin{background:var(--g-pane);border:1px solid var(--g-line);border-radius:8px}
.nx{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px;padding:12px 24px}
/* both showing: each stacks its label, name, then course and date, on rows the pair shares so they line up */
.next:has(.nx+.nx) .nx{display:grid;grid-row:span 3;grid-template-rows:subgrid;row-gap:4px;align-items:baseline}
.today .date{font-size:1rem;font-weight:700;color:var(--g-t1);text-transform:lowercase}
.nx .k{font-size:1rem;font-weight:700;color:var(--g-t1);text-transform:lowercase}
.nx .t{font-size:1rem;font-weight:700;line-height:1.35}
.nx.exam .t{font-size:1.25rem;font-weight:800;line-height:1.25;color:#fff}
.nx .none{font-style:italic;color:var(--g-t2)}
.nx .meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;font-size:.8125rem;color:var(--g-t2)}
/* the counts: a heat chip when above zero, plain text at zero (nothing here is a button) */
.counts{display:flex;flex-wrap:wrap;gap:8px 16px}
.counts span{font-size:.8125rem;line-height:1.5;color:var(--g-t2);padding:2px 0}
.counts .o,.counts .on{font-weight:700;color:var(--g-ink);padding:2px 8px;border-radius:6px}
.counts [data-due=overdue].o{background:var(--g-red)}
.counts [data-due=today].on{background:var(--g-amber)}
.counts [data-due=tomorrow].on{background:var(--g-yellow)}

/* buttons: the site's glass button, and small text actions inside items */
.act{position:relative;font:inherit;font-size:.8125rem;font-weight:600;color:var(--g-t1);background:none;border:0;padding:2px 4px;cursor:pointer;
 text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px}
.act::before{content:"";position:absolute;inset:-11px -2px}   /* a 45px hit area, same look */
.act:hover{color:#fff;text-decoration-thickness:2px}
.act.del{text-decoration-color:var(--g-red);text-decoration-thickness:2px}
.actions .act,.btn,.state{font:inherit;color:rgba(255,255,255,.92);background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.4);
 border-radius:6px;text-decoration:none;cursor:pointer;transition:background-color .3s,color .3s,box-shadow .2s ease-out}
.actions .act{font-size:1rem;min-height:44px;padding:8px 16px;white-space:nowrap}
.actions .act::before{display:none}
.actions .act.strong,.btn.primary{font-weight:700}
.actions .act:hover,.btn:hover,.bin summary:hover .state{background:rgba(255,255,255,.3);color:#fff;box-shadow:var(--g-lift)}
.btn:disabled:hover{box-shadow:none}
.btn{min-height:44px;padding:0 18px;font-weight:600}
.btn.primary{background:rgba(255,255,255,.9);color:#1C2230;border-color:transparent}
.btn.primary:hover{background:#fff;color:#1C2230}
.btn:disabled{opacity:.55;cursor:default}

/* the three columns */
.band{min-width:0;padding:24px}
.band h2{display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:1.25rem;font-weight:700;line-height:1.2;
 color:var(--g-t1);text-transform:lowercase;border-bottom:1px solid var(--g-rule);padding-bottom:8px;margin-bottom:0}
.n{font-size:.8125rem;font-weight:600;line-height:1.5;color:var(--g-t2);text-transform:none}
.grp{display:flex;align-items:center;gap:8px;font-size:1rem;font-style:italic;font-weight:400;color:var(--g-t2);text-transform:lowercase;margin:24px 0 8px}
.band h2+.grp{margin-top:16px}
.band h2+ul{margin-top:16px}
.grp[data-due]{font-weight:700;color:var(--g-t1)}
.grp[data-due]::before{content:"";width:9px;height:9px;border-radius:50%;flex:none}
.grp[data-due=overdue]::before{background:var(--g-red)}
.grp[data-due=today]::before{background:var(--g-amber)}
.grp[data-due=tomorrow]::before{background:var(--g-yellow)}
.band ul{display:grid;gap:8px}
.empty{margin-top:16px;font-style:italic;color:var(--g-t2)}

/* items: clear on the column's glass, with a wash and a slight lift under the pointer. The date chip says how soon;
   only overdue work also tints its tile, and hovering deepens that tint rather than clearing it. */
.row{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:4px;align-items:start;padding:12px 16px 12px 8px;border-radius:6px;
 transition:background-color .2s ease-out,box-shadow .2s ease-out}
.row:hover{background:var(--g-tile-hover);box-shadow:var(--g-lift)}
.row[data-due=overdue]{background:rgba(255,133,119,.14)}
.row[data-due=overdue]:hover{background:rgba(255,133,119,.2)}
.tickwrap{display:grid;place-items:center;width:44px;height:44px;margin:-11px -6px -11px -12px;cursor:pointer}
.tick{appearance:none;width:18px;height:18px;margin:0;border:1.5px solid rgba(255,255,255,.8);border-radius:4px;background:rgba(255,255,255,.06);display:grid;place-items:center;cursor:pointer}
.tick:checked{background:rgba(255,255,255,.92);border-color:transparent}
.tick:checked::after{content:"";width:5px;height:9px;border:solid #1C2230;border-width:0 2px 2px 0;transform:translateY(-1px) rotate(45deg)}
.tick:disabled{cursor:default;opacity:.7}
.t{display:block;font-size:1rem;line-height:1.35;color:var(--g-t1);text-decoration:none;overflow-wrap:anywhere}
a.t{text-decoration:underline dotted rgba(255,255,255,.45);text-decoration-thickness:1px;text-underline-offset:4px}   /* opens Moodle or Outlook */
a.t:hover{text-decoration-style:solid;text-decoration-color:currentColor}
.row.exam .t{font-weight:800;color:#fff}
.row.quiz .t{font-weight:600}
.row .meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin-top:4px;font-size:.8125rem;color:var(--g-t2)}
.kind{font-size:.8125rem;font-weight:700;line-height:1.5;padding:0 7px;border-radius:5px;font-style:normal}
.row.exam .kind{background:var(--g-lav);color:var(--g-lav-ink)}
.row.quiz .kind{border:1px solid var(--g-lav);color:var(--g-t1)}
.code{display:inline-flex;align-items:center;gap:6px;font:600 .8125rem/1.5 "Birdbrain Sans",sans-serif;color:var(--g-t1)!important;white-space:nowrap}
.code::before{content:"";display:none;width:7px;height:7px;border-radius:50%;background:var(--cc);flex:none}
.code[style*="--cc"]::before{display:block}   /* a dot only once you've picked the course's colour */
.w{line-height:1.5}
.w:empty{display:none}
[data-due=overdue]>.body .w,.nx[data-due=overdue] .w,
[data-due=today]>.body .w,.nx[data-due=today] .w,
[data-due=tomorrow]>.body .w,.nx[data-due=tomorrow] .w{color:var(--g-ink);font-weight:700;padding:0 7px;border-radius:5px}
[data-due=overdue]>.body .w,.nx[data-due=overdue] .w{background:var(--g-red)}
[data-due=today]>.body .w,.nx[data-due=today] .w{background:var(--g-amber)}
[data-due=tomorrow]>.body .w,.nx[data-due=tomorrow] .w{background:var(--g-yellow)}
.unsure{font-style:italic}
.row.past .t,.row.past .w{color:var(--g-t2)}
.row.is-done .t{color:var(--g-t2);text-decoration:line-through;font-weight:400}
.row.leaving{opacity:0;transform:translateX(8px);transition:opacity .18s ease-in,transform .18s ease-in}
.detail{font-size:.8125rem;line-height:1.5;color:var(--g-t2);margin-top:6px;overflow-wrap:anywhere}
.acts{display:inline-flex;gap:.3rem;margin-left:.2rem}
/* Archive: on every open item, shown under the pointer or while the tile has keyboard focus (always, on touch) */
.act.arch{margin-left:auto;opacity:0;transition:opacity .2s ease-out}
.row:hover .act.arch,.row:focus-within .act.arch{opacity:1}
@media (hover:none){.act.arch{opacity:1}}
.kw-msg:empty{display:none}
.sub-options{margin:4px 0 8px 28px;padding-left:16px;border-left:1px solid var(--g-line)}
.sub-options .field{margin-bottom:4px}
.warn-note{color:var(--g-t1);max-width:36rem}
/* the shortcut list: each key a small glass cap */
kbd{display:inline-block;min-width:26px;padding:0 7px;font:inherit;font-size:.8125rem;font-weight:700;line-height:1.6;text-align:center;
 color:var(--g-t1);background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.4);border-radius:5px}
.keys{display:grid;gap:10px;margin:0 0 12px}
.keys div{display:grid;grid-template-columns:104px 1fr;align-items:baseline;gap:12px}
.keys dt{color:var(--g-t2);font-size:.8125rem}
.keys dd{margin:0}
.keys .or{margin:0 6px;font-size:.8125rem;color:var(--g-t2)}
#keys-sec .sub{margin:16px 0 8px}#keys-sec .sub:first-of-type{margin-top:0}

/* all clear: Now is empty, so the lookout's bird rests on its branch; and a quiet line once today alone is done */
.clear{display:grid;justify-items:start;gap:4px;margin-top:24px}
.perch{width:112px;height:70px;margin:0 0 8px -6px;color:var(--g-t1);overflow:visible}
.perch .bird{fill:currentColor}
.perch .branch,.perch .legs{fill:none;stroke:currentColor;stroke-linecap:round}.perch .branch{stroke-width:2.2;opacity:.55}.perch .legs{stroke-width:1.6}
.perch .wing{fill:none;stroke:rgba(0,0,0,.28);stroke-width:1.4;stroke-linecap:round}
.perched{transform-box:fill-box;transform-origin:50% 100%}
.clear-head{font-size:1.25rem;font-weight:700;line-height:1.2;color:var(--g-t1);text-transform:lowercase}
.clear-sub{color:var(--g-t2)}
.clear-next{margin-top:8px;color:var(--g-t1)}
.dayclear{display:flex;align-items:center;gap:8px;font-style:italic;color:var(--g-t2);text-transform:lowercase;margin:24px 0 8px}
.band h2+.dayclear{margin-top:16px}
.wingmark{width:18px;height:9px;flex:none;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round}

/* motion: a ticked item lifts off the glass as a small card and flies into Completed (and back on Undo);
   when you finish the last thing due today, one bird flies in and lands on the empty branch in Now.
   report.py's script drives both. */
.row.lifted{opacity:0}
.fly{position:fixed;z-index:40;margin:0;pointer-events:none}
.fly .row,.fly .row[data-due]{background:var(--g-sheet);box-shadow:var(--g-lift),0 0 0 1px rgba(255,255,255,.35);transition:none}
.clear.waiting .perched,.dayclear.waiting .wingmark{opacity:0}   /* the branch is empty until the bird lands */
.flier{position:fixed;left:0;top:0;z-index:45;pointer-events:none;offset-rotate:0deg;color:#fff;filter:drop-shadow(0 1px 2px rgba(0,0,0,.55))}
.flier svg{display:block;width:34px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;
 transform-origin:50% 70%;animation:flap .26s ease-in-out infinite alternate}
@keyframes flap{to{transform:scaleY(-.6)}}

/* the Custom theme: empty photo halves, and the panel for its photos and accent */
/* no photo yet: the half fills its side of the card like any other, faintly washed, split down the middle */
.half.photo.no-photo{flex-direction:column;align-items:flex-start;justify-content:flex-end;gap:2px;background:rgba(255,255,255,.06)}
.half.photo.no-photo+.half.photo.no-photo{border-left:1px dashed rgba(255,255,255,.35)}
.half.photo em{font-size:.8125rem;font-style:normal;color:var(--g-t2)}
.half.photo:not(.no-photo) em{display:none}
.custom-panel{margin:0 0 16px;padding:16px 20px 12px;border:1px solid var(--g-line);border-radius:8px;background:rgba(255,255,255,.04)}
.custom-panel .sub{margin-top:0}
.slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.slot{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.slot-pic{flex:1 0 100%;height:96px;border-radius:6px;background:center/cover no-repeat;display:flex;align-items:flex-end;padding:8px;
 box-shadow:inset 0 0 0 1px var(--g-line)}
.slot-pic.no-photo{background:rgba(255,255,255,.04);box-shadow:none;border:1px dashed rgba(255,255,255,.5)}
.slot-pic span{font-size:.8125rem;font-weight:700;color:#fff;background:rgba(0,0,0,.6);padding:0 6px;border-radius:4px}
.file-btn{display:inline-flex;align-items:center}
.file-btn:has(input:focus-visible){outline:2px solid var(--g-focus);outline-offset:2px}
.cpick{display:flex;align-items:center;gap:12px;min-height:44px;cursor:pointer;margin-top:4px}
.cpick input[type=color]{appearance:none;-webkit-appearance:none;flex:none;width:44px;height:44px;padding:7px;margin:0 -7px;border:0;background:none;cursor:pointer}
.cpick input[type=color]::-webkit-color-swatch-wrapper{padding:0}
.cpick input[type=color]::-webkit-color-swatch{border:1px solid rgba(255,255,255,.6);border-radius:8px}
.cpick em{font-style:normal;font-size:.8125rem;color:var(--g-t2)}

/* completed + archived: collapsible glass panels */
.bins{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:24px;align-items:start}
/* each bin opens in place, in its own column, so opening one never moves the other */
.bin{padding:16px 24px}
.bin summary{position:relative;list-style:none;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;cursor:pointer;width:fit-content;min-height:44px}
.bin summary::-webkit-details-marker{display:none}
.bin-title{font-size:1.25rem;font-weight:700;color:var(--g-t1);text-transform:lowercase}
.state{font-size:.8125rem;font-weight:600;padding:4px 12px}
.state::after{content:"Show"}
.bin[open] .state::after{content:"Hide"}
.bin summary.pulse .bin-title{animation:pulse 1s ease-out}
@keyframes pulse{from{color:var(--g-yellow)}}
.hint{font-size:.8125rem;color:var(--g-t2);margin:8px 0 16px;max-width:44rem}
.bin-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,19rem),1fr));gap:8px 16px;align-items:start}

/* dialogs: a denser sheet of the same glass */
.sheet-dialog{width:min(620px,calc(100vw - 32px));max-height:min(88vh,940px);padding:0;border:0;border-radius:10px;color:var(--g-t1);
 background:var(--g-sheet);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);outline:2px solid var(--g-edge);
 box-shadow:inset 3px 3px 6px rgba(255,255,255,.28),inset -3px -3px 6px rgba(0,0,0,.35)}
.sheet-dialog::backdrop{background:rgba(8,12,22,.35);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
.sheet-dialog[open]{animation:sheet-in .2s ease-out}
@keyframes sheet-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.sheet{padding:24px 28px 28px;margin:0}
.sheet-head{display:flex;justify-content:space-between;align-items:center;gap:12px;border-bottom:1px solid var(--g-rule);padding-bottom:10px;margin-bottom:.4rem}
.sheet-head h2{font-size:1.25rem;font-weight:700;text-transform:lowercase}
/* Settings: tabs across the top and one pane at a time; the dialog keeps its height as you switch */
#settings{height:min(88vh,720px);overflow:hidden}
#settings[open]{display:flex;flex-direction:column}
#settings .sheet{flex:1;min-height:0;display:flex;flex-direction:column;padding:0}
#settings .sheet-head{padding:24px 28px 10px;margin:0;border-bottom:0}
.tabs{flex:none;display:flex;gap:4px;padding:0 18px;border-bottom:1px solid var(--g-rule);overflow-x:auto;scrollbar-width:none}
.tab{font:inherit;font-size:1rem;font-weight:600;color:var(--g-t2);background:none;border:0;border-bottom:2px solid transparent;margin-bottom:-1px;
 padding:0 10px;min-height:44px;min-width:44px;cursor:pointer;white-space:nowrap;transition:color .15s}
.tab:hover{color:#fff}
.tab[aria-selected=true]{color:var(--g-t1);border-bottom-color:var(--g-t1)}
.tab:focus-visible{outline:2px solid var(--g-focus);outline-offset:-6px;border-radius:6px}
.pane{flex:1;min-height:0;overflow-y:auto;padding:0 28px 28px}
.pane:focus-visible{outline:2px solid var(--g-focus);outline-offset:-4px}
.pane::-webkit-scrollbar{width:14px}
.pane::-webkit-scrollbar-track{background:transparent;margin:8px 0}
.pane::-webkit-scrollbar-thumb{background:rgba(255,255,255,.2);border:4px solid transparent;background-clip:padding-box;border-radius:999px;
 box-shadow:inset 1px 1px 1px rgba(255,255,255,.3)}
.pane::-webkit-scrollbar-thumb:hover{background-color:rgba(255,255,255,.36)}
.pane .set-sec:first-child{padding-top:20px}
.set-sec{padding-top:1.4rem}
.set-sec .sub{font-size:.8125rem;font-weight:600;color:var(--g-t2);margin:16px 0 8px}
.set-sec h3{font-size:1rem;font-style:italic;font-weight:400;color:var(--g-t2);text-transform:lowercase;margin-bottom:.7rem}
.themes{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px 12px;margin-bottom:1rem}
.theme-opt{position:relative;display:grid;gap:6px;cursor:pointer}
.theme-opt input,.seg input{position:absolute;opacity:0;pointer-events:none}
.swatch{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--g-line);border-radius:6px;overflow:hidden}
.half{padding:8px;font-size:.8125rem;font-weight:600;white-space:nowrap;overflow:hidden}
.half.photo{min-height:64px;display:flex;align-items:flex-end;background:center/cover no-repeat}
.half.photo span{font-size:.8125rem;font-weight:700;color:#fff;background:rgba(0,0,0,.6);padding:0 6px;border-radius:4px}
.theme-name{font-size:.8125rem;color:var(--g-t2)}
.half{position:relative;cursor:pointer}
.half:hover{filter:brightness(1.1)}
.half:has(input:checked){box-shadow:inset 0 0 0 2px #FFFFFF,inset 0 0 0 4px #000000}
.theme-opt:has(input:checked) .theme-name{color:var(--g-t1);font-weight:700}
.theme-opt:has(input:focus-visible) .swatch{outline:2px solid var(--g-focus);outline-offset:4px}
.seg{display:flex;flex-wrap:wrap;gap:8px}
.seg label{position:relative;cursor:pointer}
.seg span{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border:1px solid var(--g-line);border-radius:6px;color:var(--g-t2);background:rgba(255,255,255,.04);transition:background-color .15s,box-shadow .2s ease-out}
.seg label:hover span{color:#fff;background:rgba(255,255,255,.12);box-shadow:var(--g-lift)}
.seg input:checked+span{color:#1C2230;background:rgba(255,255,255,.9);border-color:transparent;font-weight:700}
.seg label:has(input:focus-visible){outline:2px solid var(--g-focus);outline-offset:2px;border-radius:6px}
fieldset.field{border:0;padding:0;margin:0 0 1rem}
.field{display:grid;gap:6px;margin:0 0 1rem;min-width:0}
.field>span,.field legend{font-size:.8125rem;font-weight:600;color:var(--g-t2);padding:0}
.field em{font-style:italic;font-weight:400}
.field input,.nick{font:inherit;font-size:1rem;color:#fff;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.3);border-radius:6px;padding:10px 12px;min-height:44px;min-width:0;width:100%}
.field input:focus,.nick:focus{border-color:#fff;outline:2px solid var(--g-focus);outline-offset:1px}
.nick::placeholder,.field input::placeholder{color:rgba(255,255,255,.7)}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-error{font-size:1rem;color:#FFC2B8;margin-bottom:.6rem}.form-error:empty{display:none}
.actions-row{display:flex;justify-content:flex-end;align-items:center;gap:1rem;margin-top:.6rem}
.scan-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px}.scan-row .field{margin:0;flex:1 1 200px}
.btn-row{display:flex;flex-wrap:wrap;gap:10px;margin:.2rem 0 .4rem}
.check{display:flex;align-items:center;gap:10px;min-height:44px;cursor:pointer;color:var(--g-t1)}
.check input{width:18px;height:18px;margin:0;flex:none;accent-color:#FFFFFF}
.sound-row{display:flex;flex-wrap:wrap;align-items:center;gap:0 18px}
/* the scrollbar: the panels' own tinted glass with the frame's white edge and bevel, blurring what's behind */
:root{--sb-track:rgba(255,255,255,.07);--sb-track-edge:rgba(255,255,255,.2);--sb-blur:blur(10px) saturate(1.2);
 --sb-thumb:var(--g-glass);--sb-thumb-hover:var(--g-sheet);--sb-thumb-edge:rgba(255,255,255,.7);
 --sb-bevel:inset 1px 1px 2px rgba(255,255,255,.4),inset -1px -1px 2px rgba(0,0,0,.4),0 1px 6px rgba(0,0,0,.3)}
.sheet-dialog::-webkit-scrollbar{width:14px}
.sheet-dialog::-webkit-scrollbar-track{background:transparent;margin:12px 0}
.sheet-dialog::-webkit-scrollbar-thumb{background:rgba(255,255,255,.2);border:4px solid transparent;background-clip:padding-box;border-radius:999px;
 box-shadow:inset 1px 1px 1px rgba(255,255,255,.3)}
.sheet-dialog::-webkit-scrollbar-thumb:hover{background-color:rgba(255,255,255,.36)}
:root{--tb-fg:#FFFFFF;--tb-hover:rgba(255,255,255,.14);--tb-scrolled:var(--g-glass);--tb-shadow:0 0 5px rgba(0,0,0,.55);
--tb-bg:linear-gradient(rgba(0,0,0,.36),rgba(0,0,0,.12) 70%,rgba(0,0,0,0))}   /* keeps the buttons readable on bright skies */
.app-window .wrap{margin-top:56px}
.btn.danger{border-color:var(--g-red)}
.btn.danger:hover{background:rgba(255,133,119,.25)}
.kw-list li{display:flex;flex-wrap:wrap;align-items:center;gap:4px 14px;padding:7px 0;border-bottom:1px solid var(--g-rule)}
.kw{font-weight:700}.kw-n{flex:1;font-size:.8125rem;color:var(--g-t2)}.kw-empty{color:var(--g-t2);font-style:italic;border:0!important}
.kw-add{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px;margin-top:.8rem}.kw-add .field{margin:0;flex:1 1 220px}
.gone{grid-column:1/-1;justify-self:center;font-size:1.25rem;color:var(--g-t1);margin:4rem 0}
.courses li{display:grid;grid-template-columns:32px minmax(96px,auto) 1fr auto;grid-template-areas:"color code nick reset" ". warn warn warn";align-items:center;column-gap:12px;padding:6px 0}
.courses input[type=color]{grid-area:color;appearance:none;-webkit-appearance:none;width:44px;height:44px;padding:8px;margin:-8px;border:0;border-radius:50%;background:none;cursor:pointer}
.courses input[type=color]::-webkit-color-swatch-wrapper{padding:0}
.courses input[type=color]::-webkit-color-swatch{border:1px solid rgba(255,255,255,.6);border-radius:50%}
.courses li.unset input[type=color]::-webkit-color-swatch{background:transparent!important;border:1.5px dashed rgba(255,255,255,.7)}   /* no colour picked */
.cc{grid-area:code;font-size:1rem;font-weight:700;color:var(--g-t1)!important;white-space:nowrap}
.nick{grid-area:nick;padding:8px 10px}
.reset{grid-area:reset}
.reset:disabled{opacity:.5;cursor:default;text-decoration:none}
.courses .warn{grid-area:warn;font-size:.8125rem;color:#FFC2B8;margin-top:2px}.courses .warn:empty{display:none}
#toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,10px);max-width:calc(100vw - 32px);padding:10px 18px;border-radius:8px;
 background:rgba(30,35,46,.88);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);outline:1px solid rgba(255,255,255,.5);
 color:#fff;font-weight:600;opacity:0;pointer-events:none;transition:opacity .2s ease-out,transform .2s ease-out}
#toast.show{opacity:1;transform:translate(-50%,0)}
#toast.has-action.show{pointer-events:auto;display:flex;align-items:center;gap:16px}
.toast-undo{font:inherit;font-weight:700;color:#fff;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.4);border-radius:6px;
 min-height:32px;padding:0 12px;cursor:pointer}
.toast-undo:hover{background:rgba(255,255,255,.3)}

/* narrower windows: two columns, then one (the site's own breakpoints) */
@media (max-width:1150px){
.wrap,:root[data-frame=narrow] .wrap{grid-template-columns:repeat(2,minmax(0,1fr));width:calc(100% - 2 * max(16px,4vw))}
h1{grid-column:1/-1}
.today{grid-column:1;grid-row:3}.actions{grid-column:2;grid-row:3}
.next{grid-row:4}
.bands{grid-row:5}.band:nth-child(3){grid-column:1/-1}.bins{grid-row:6}
.band:nth-child(3) ul{grid-template-columns:repeat(auto-fill,minmax(min(100%,19rem),1fr));column-gap:16px}}   /* later, full width: two lists side by side */
@media (max-width:768px){
.wrap,:root[data-frame=narrow] .wrap{grid-template-columns:minmax(0,1fr);margin:24px 8px;width:auto;padding:24px 16px}
h1{font-size:1.75rem}
.actions{grid-column:1;grid-row:4;justify-self:start}   /* after today's date and counts, as in the page's order */
.today,.band:nth-child(3){grid-column:1}.today{grid-row:3}.next{grid-row:5}.bands{grid-row:6}.bins{grid-row:7}
.sheet{padding:18px}.field-row{grid-template-columns:1fr}
#settings{height:calc(100vh - 32px)}#settings .sheet-head{padding:18px 18px 8px}.tabs{padding:0 8px;gap:0;justify-content:space-between}.tab{padding:0 5px}.pane{padding:0 18px 22px}
.courses li{grid-template-columns:32px 1fr auto;grid-template-areas:"color code reset" ". nick nick" ". warn warn";row-gap:6px}}
.no-anim *{transition:none!important}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""
