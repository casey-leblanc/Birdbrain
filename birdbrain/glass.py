"""The Frosted glass layout (the default), modelled on caseyleblanc.dev.

One frosted panel floats over a photo and holds everything: the title centred
at the top, a strip of three small glass panels (today, next exam, next quiz),
then Now / This week / Later as three glass columns, laid out like the site's
blog (a wider middle column). Items are small glass tiles. Headings are
lowercase and dates italic, as on the site; the font is Atkinson Hyperlegible.

Every theme is a colour scheme here (SCHEMES): its own photo for light mode
(day) and dark mode (night), a glass tint, a title colour and an exam-chip
colour. The photos are in assets/backgrounds, credited in CREDITS.txt there.

Urgency is carried by colour on the due date, the same in every scheme:
  overdue   red edge on the tile, a red tint, and a solid red chip on the date
  today     amber edge, tint and chip
  tomorrow  yellow edge and chip
  soon      a white edge and an outlined chip (two or three days away)
Exams get a solid chip in the scheme's exam colour and a bold title, quizzes an
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
SCHEMES = {
    "forest": dict(common=dict(title="rgba(255,255,255,.82)", lav="#DCD0FF", lav_ink="#21173F", focus="#FFFFFF"),
                   light=dict(glass="rgba(36,41,51,.76)", sheet="rgba(34,39,50,.92)", bg="#7FA3D2"),
                   dark=dict(glass="rgba(16,22,34,.64)", sheet="rgba(18,24,36,.92)", bg="#0A1230")),
    "birdbrain": dict(common=dict(title="#DDD5FF", lav="#D9D0FF", lav_ink="#21173F", focus="#FFFFFF"),
                      light=dict(glass="rgba(42,34,74,.74)", sheet="rgba(36,30,64,.92)", bg="#9C8BC9"),
                      dark=dict(glass="rgba(26,20,50,.66)", sheet="rgba(24,20,46,.92)", bg="#2A2150")),
    "night": dict(common=dict(title="#CDEBE2", lav="#A8E6D8", lav_ink="#0F2A24", focus="#FFD28A"),
                  light=dict(glass="rgba(20,38,32,.76)", sheet="rgba(20,36,30,.92)", bg="#6E8F4E"),
                  dark=dict(glass="rgba(12,24,20,.66)", sheet="rgba(12,24,20,.92)", bg="#10170F")),
    "contrast": dict(common=dict(title="#FFFFFF", lav="#7FE0FF", lav_ink="#000000", focus="#FFE14D",
                                 t2="#FFFFFF", edge="#FFFFFF", line="rgba(255,255,255,.55)"),
                     light=dict(glass="rgba(0,0,0,.86)", sheet="rgba(0,0,0,.95)", bg="#BDBDBD"),
                     dark=dict(glass="rgba(0,0,0,.84)", sheet="rgba(0,0,0,.95)", bg="#1A1A1A")),
    "dusk": dict(common=dict(title="#F8D6E0", lav="#A9DBF2", lav_ink="#0E2533", focus="#F5B38A"),
                 light=dict(glass="rgba(36,34,64,.72)", sheet="rgba(34,32,60,.92)", bg="#C98AA0"),
                 dark=dict(glass="rgba(14,26,40,.72)", sheet="rgba(16,24,38,.92)", bg="#1F4A5C")),
}


def photo_name(theme: str, mode: str, thumb: bool = False) -> str:
    return f"{theme}-{mode}" + ("-thumb" if thumb else "")


def file_url(name: str) -> str | None:
    """A photo as a file:// address, for the read-only copy of the page."""
    path = BG_DIR / f"{name}.jpg"
    return path.as_uri() if path.exists() else None


def css(photo: Callable[[str], str | None]) -> str:
    """The stylesheet, with one block of colours and a photo address per scheme and mode.
    `photo(name)` gives the address of assets/backgrounds/<name>.jpg, or None to show the fallback colour."""
    blocks = []
    for key, sc in SCHEMES.items():
        for mode in ("light", "dark"):
            v = {**sc["common"], **sc[mode]}
            url = photo(photo_name(key, mode))
            v["photo"] = f'url("{url}")' if url else "none"
            props = ";".join(f"--g-{k.replace('_', '-')}:{val}" for k, val in v.items())
            blocks.append(f":root[data-theme={key}][data-mode={mode}]{{{props}}}")
    return BASE + "".join(blocks) + CSS


BASE = """
:root{--g-t1:rgba(255,255,255,.96);--g-t2:rgba(255,255,255,.88);--g-edge:rgba(255,255,255,.6);
--g-line:rgba(255,255,255,.2);--g-rule:rgba(255,255,255,.16);--g-glass:rgba(36,41,51,.76);--g-pane:rgba(255,255,255,.055);
--g-tile:rgba(255,255,255,.045);--g-tile-hover:rgba(255,255,255,.085);--g-sheet:rgba(34,39,50,.92);
--g-red:#FF8577;--g-amber:#FFBC5C;--g-yellow:#FFE27D;--g-lav:#DCD0FF;--g-ink:#20140E;--g-lav-ink:#21173F;
--g-title:rgba(255,255,255,.82);--g-focus:#FFFFFF;--g-bg:#7FA3D2;--g-photo:none;color-scheme:dark}
"""

CSS = """
*{box-sizing:border-box}
html{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.3) transparent}
body{margin:0;min-height:100vh;background:var(--g-bg);color:var(--g-t1);font:400 16px/1.5 "Birdbrain Sans","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
body::before{content:"";position:fixed;inset:-10px;z-index:-1;background:var(--g-photo) center/cover no-repeat,var(--g-bg)}
body.static .needs-app{display:none!important}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
p,h1,h2,h3,ul{margin:0;padding:0}ul{list-style:none}
:focus-visible{outline:2px solid var(--g-focus);outline-offset:3px;border-radius:4px}

/* the frosted frame: title, a strip of three small panels, three glass columns */
.wrap{width:min(1500px,calc(100% - 2 * max(16px,4vw)));margin:44px auto 60px;padding:30px;
 display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr) minmax(0,1fr);column-gap:25px;row-gap:20px;align-items:start;
 background:var(--g-glass);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);outline:2px solid var(--g-edge);border-radius:10px;
 box-shadow:inset 3px 3px 6px rgba(255,255,255,.4),inset -3px -3px 6px rgba(0,0,0,.4)}
.top,.next{display:contents}
h1{grid-column:1/-1;grid-row:1;justify-self:center;font-size:3rem;font-weight:700;line-height:1.1;letter-spacing:.01em;color:var(--g-title);text-transform:lowercase}
.status{grid-column:1/-1;grid-row:2;justify-self:center;text-align:center;max-width:60ch;margin-top:-14px;font-size:.85rem;color:var(--g-t2)}
.status.problem{background:var(--g-red);color:var(--g-ink);font-weight:700;padding:2px 10px;border-radius:6px}
.actions{grid-column:3;grid-row:1;justify-self:end;align-self:start;display:flex;gap:10px}
.today{grid-column:1;grid-row:3}.nx.exam{grid-column:2;grid-row:3}.nx.quiz{grid-column:3;grid-row:3}
.bands{grid-column:1/-1;grid-row:4;display:grid;grid-template-columns:subgrid;row-gap:20px;align-items:stretch}
.bins{grid-column:1/-1;grid-row:5}

/* glass panels (the site's sidebar panels and blog entries) */
.today,.nx,.band,.bin{background:var(--g-pane);border:1px solid var(--g-line);border-radius:8px;
 box-shadow:inset 1px 1px 3px rgba(255,255,255,.15),inset -1px -1px 3px rgba(0,0,0,.2)}
.today,.nx{align-self:stretch;padding:16px 18px}
.today .date,.nx .k{font-size:1.15rem;font-weight:700;color:var(--g-t1);text-transform:lowercase;
 border-bottom:1px solid var(--g-rule);padding-bottom:6px;margin-bottom:12px}
.nx .k{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:2px 12px}
.nx .span{font-size:.85rem;font-weight:400;font-style:italic;color:var(--g-t2)}
.nx .t{font-size:1.25rem;font-weight:700;line-height:1.25;margin-bottom:10px}
.nx.exam .t{font-size:1.4rem;font-weight:800;color:#fff}
.nx .none{font-style:italic;color:var(--g-t2)}
.nx .meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;font-size:.9rem;color:var(--g-t2)}
.counts{display:flex;flex-wrap:wrap;gap:8px}
.counts span{font-size:.95rem;color:var(--g-t2);padding:3px 10px;border-radius:6px;border:1px solid var(--g-line)}
.counts .o,.counts .on{font-weight:700;border-color:transparent;color:var(--g-ink)}
.counts [data-due=overdue].o{background:var(--g-red)}
.counts [data-due=today].on{background:var(--g-amber)}
.counts [data-due=tomorrow].on{background:var(--g-yellow)}

/* buttons: the site's glass button, and small text actions inside items */
.act{position:relative;font:inherit;font-size:.8rem;font-weight:600;color:var(--g-t1);background:none;border:0;padding:2px 4px;cursor:pointer;
 text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px}
.act::before{content:"";position:absolute;inset:-10px -2px}   /* 44px hit area, same look */
.act:hover{color:#fff;text-decoration-thickness:2px}
.act.del{text-decoration-color:var(--g-red);text-decoration-thickness:2px}
.actions .act,.btn,.state{font:inherit;color:rgba(255,255,255,.92);background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.4);
 border-radius:6px;text-decoration:none;cursor:pointer;transition:background-color .3s,color .3s}
.actions .act{font-size:1rem;min-height:44px;padding:8px 16px;white-space:nowrap}
.actions .act::before{display:none}
.actions .act.strong,.btn.primary{font-weight:700}
.actions .act:hover,.btn:hover,.bin summary:hover .state{background:rgba(255,255,255,.3);color:#fff}
.btn{min-height:44px;padding:0 18px;font-weight:600}
.btn.primary{background:rgba(255,255,255,.9);color:#1C2230;border-color:transparent}
.btn.primary:hover{background:#fff;color:#1C2230}
.btn:disabled{opacity:.55;cursor:default}

/* the three columns */
.band{min-width:0;padding:18px 18px 22px}
.band h2{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:1.5rem;font-weight:700;line-height:1.2;
 color:var(--g-t1);text-transform:lowercase;border-bottom:1px solid var(--g-rule);padding-bottom:8px;margin-bottom:4px}
.n{font-size:.8rem;font-weight:700;line-height:1.6;color:#fff;background:rgba(0,0,0,.28);border-radius:6px;padding:0 8px;text-transform:none}
.grp{display:flex;align-items:center;gap:8px;font-size:.95rem;font-style:italic;font-weight:400;color:var(--g-t2);text-transform:lowercase;margin:18px 0 8px}
.grp[data-due]{font-weight:700;color:var(--g-t1)}
.grp[data-due]::before{content:"";width:9px;height:9px;border-radius:50%;flex:none}
.grp[data-due=overdue]::before{background:var(--g-red)}
.grp[data-due=today]::before{background:var(--g-amber)}
.grp[data-due=tomorrow]::before{background:var(--g-yellow)}
.band ul{display:grid;gap:8px}
.empty{margin-top:16px;font-style:italic;color:var(--g-t2)}

/* items: glass tiles; the left edge and the date chip show how soon */
.row{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:4px;align-items:start;padding:9px 12px 9px 8px;border-radius:6px;
 background:var(--g-tile);border-left:3px solid transparent;transition:background-color .2s ease-in-out,transform .2s ease-in-out}
.row:hover{background:var(--g-tile-hover);transform:translateX(2px)}
.row[data-due=overdue]{border-left-color:var(--g-red);background:rgba(255,133,119,.14)}
.row[data-due=today]{border-left-color:var(--g-amber);background:rgba(255,188,92,.12)}
.row[data-due=tomorrow]{border-left-color:var(--g-yellow);background:rgba(255,226,125,.06)}
.row[data-due=soon]{border-left-color:rgba(255,255,255,.55)}
.row[data-due]:hover{background:var(--g-tile-hover)}
.tickwrap{display:grid;place-items:center;width:44px;height:44px;margin:-11px -6px -11px -12px;cursor:pointer}
.tick{appearance:none;width:18px;height:18px;margin:0;border:1.5px solid rgba(255,255,255,.8);border-radius:4px;background:rgba(255,255,255,.06);display:grid;place-items:center;cursor:pointer}
.tick:checked{background:rgba(255,255,255,.92);border-color:transparent}
.tick:checked::after{content:"";width:5px;height:9px;border:solid #1C2230;border-width:0 2px 2px 0;transform:translateY(-1px) rotate(45deg)}
.tick:disabled{cursor:default;opacity:.7}
.t{display:block;font-size:1rem;line-height:1.35;color:var(--g-t1);text-decoration:none;overflow-wrap:anywhere}
a.t:hover{text-decoration:underline;text-underline-offset:3px}
.row.exam .t{font-weight:800;color:#fff}
.row.quiz .t{font-weight:600}
.row .meta{display:flex;flex-wrap:wrap;align-items:center;gap:5px 8px;margin-top:5px;font-size:.8rem;color:var(--g-t2)}
.kind{font-size:.75rem;font-weight:700;line-height:1.6;padding:0 7px;border-radius:5px;font-style:normal}
.row.exam .kind{background:var(--g-lav);color:var(--g-lav-ink)}
.row.quiz .kind{border:1px solid var(--g-lav);color:var(--g-t1)}
.code{display:inline-flex;align-items:center;gap:6px;font:700 .8rem/1.6 "Birdbrain Sans",sans-serif;color:var(--g-t1)!important;white-space:nowrap}
.code::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--cc,rgba(255,255,255,.55));flex:none}
.w{line-height:1.6}
.w:empty{display:none}
[data-due=overdue]>.body .w,.nx[data-due=overdue] .w,
[data-due=today]>.body .w,.nx[data-due=today] .w,
[data-due=tomorrow]>.body .w,.nx[data-due=tomorrow] .w{color:var(--g-ink);font-weight:700;padding:0 7px;border-radius:5px}
[data-due=overdue]>.body .w,.nx[data-due=overdue] .w{background:var(--g-red)}
[data-due=today]>.body .w,.nx[data-due=today] .w{background:var(--g-amber)}
[data-due=tomorrow]>.body .w,.nx[data-due=tomorrow] .w{background:var(--g-yellow)}
[data-due=soon]>.body .w,.nx[data-due=soon] .w{color:var(--g-t1);padding:0 6px;border:1px solid rgba(255,255,255,.55);border-radius:5px}
.unsure{font-style:italic}
.row.past .t,.row.past .w{color:var(--g-t2)}
.row.is-done .t{color:var(--g-t2);text-decoration:line-through;font-weight:400}
.row.leaving{opacity:0;transform:translateX(8px);transition:opacity .18s ease-in,transform .18s ease-in}
.detail{font-size:.85rem;line-height:1.5;color:var(--g-t2);margin-top:6px;overflow-wrap:anywhere}
.acts{display:inline-flex;gap:.3rem;margin-left:.2rem}

/* completed + archived: collapsible glass panels */
.bins{display:grid;gap:20px}
.bin{padding:14px 18px}
.bin summary{position:relative;list-style:none;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;cursor:pointer;width:fit-content;min-height:44px}
.bin summary::-webkit-details-marker{display:none}
.bin-title{font-size:1.25rem;font-weight:700;color:var(--g-t1);text-transform:lowercase}
.state{font-size:.85rem;font-weight:600;padding:4px 12px}
.state::after{content:"Show"}
.bin[open] .state::after{content:"Hide"}
.bin summary.pulse .bin-title{animation:pulse 1s ease-out}
@keyframes pulse{from{color:var(--g-yellow)}}
.hint{font-size:.85rem;color:var(--g-t2);margin:.4rem 0 .9rem;max-width:44rem}
.bin-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,19rem),1fr));gap:8px 12px;align-items:start}

/* dialogs: a denser sheet of the same glass */
.sheet-dialog{width:min(620px,calc(100vw - 32px));max-height:min(88vh,940px);padding:0;border:0;border-radius:10px;color:var(--g-t1);
 background:var(--g-sheet);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);outline:2px solid var(--g-edge);
 box-shadow:inset 3px 3px 6px rgba(255,255,255,.28),inset -3px -3px 6px rgba(0,0,0,.35)}
.sheet-dialog::backdrop{background:rgba(8,12,22,.35);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
.sheet-dialog[open]{animation:sheet-in .2s ease-out}
@keyframes sheet-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.sheet{padding:24px 28px 28px;margin:0}
.sheet-head{display:flex;justify-content:space-between;align-items:center;gap:12px;border-bottom:1px solid var(--g-rule);padding-bottom:10px;margin-bottom:.4rem}
.sheet-head h2{font-size:1.5rem;font-weight:700;text-transform:lowercase}
.set-sec{padding-top:1.4rem}
.set-sec h3{font-size:1rem;font-style:italic;font-weight:400;color:var(--g-t2);text-transform:lowercase;margin-bottom:.7rem}
.themes{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px 12px;margin-bottom:1rem}
.theme-opt{position:relative;display:grid;gap:6px;cursor:pointer}
.theme-opt input,.seg input{position:absolute;opacity:0;pointer-events:none}
.swatch{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--g-line);border-radius:6px;overflow:hidden}
.half{padding:9px 7px;font-size:.8rem;font-weight:600;white-space:nowrap;overflow:hidden}
.half.photo{min-height:64px;display:flex;align-items:flex-end;background:center/cover no-repeat}
.half.photo span{font-size:.75rem;font-weight:700;color:#fff;background:rgba(0,0,0,.6);padding:0 6px;border-radius:4px}
.theme-name{font-size:.85rem;color:var(--g-t2)}
.theme-opt:has(input:checked) .swatch{outline:2px solid var(--g-t1);outline-offset:2px}
.theme-opt:has(input:checked) .theme-name{color:var(--g-t1);font-weight:700}
.theme-opt:has(input:focus-visible) .swatch{outline:2px solid var(--g-focus);outline-offset:4px}
.seg{display:flex;flex-wrap:wrap;gap:8px}
.seg label{position:relative;cursor:pointer}
.seg span{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border:1px solid var(--g-line);border-radius:6px;color:var(--g-t2);background:rgba(255,255,255,.04)}
.seg label:hover span{color:#fff;background:rgba(255,255,255,.12)}
.seg input:checked+span{color:#1C2230;background:rgba(255,255,255,.9);border-color:transparent;font-weight:700}
.seg label:has(input:focus-visible){outline:2px solid var(--g-focus);outline-offset:2px;border-radius:6px}
fieldset.field{border:0;padding:0;margin:0 0 1rem}
.field{display:grid;gap:6px;margin:0 0 1rem;min-width:0}
.field>span,.field legend{font-size:.85rem;font-weight:600;color:var(--g-t2);padding:0}
.field em{font-style:italic;font-weight:400}
.field input,.nick{font:inherit;font-size:1rem;color:#fff;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.3);border-radius:6px;padding:10px 12px;min-height:44px;min-width:0;width:100%}
.field input:focus,.nick:focus{border-color:#fff;outline:2px solid var(--g-focus);outline-offset:1px}
.nick::placeholder{color:rgba(255,255,255,.7)}
.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.form-error{font-size:1rem;color:#FFC2B8;margin-bottom:.6rem}.form-error:empty{display:none}
.actions-row{display:flex;justify-content:flex-end;align-items:center;gap:1rem;margin-top:.6rem}
.scan-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px}.scan-row .field{margin:0;flex:1 1 200px}
.courses li{display:grid;grid-template-columns:32px minmax(96px,auto) 1fr auto;grid-template-areas:"color code nick reset" ". warn warn warn";align-items:center;column-gap:12px;padding:6px 0}
.courses input[type=color]{grid-area:color;appearance:none;-webkit-appearance:none;width:44px;height:44px;padding:8px;margin:-8px;border:0;border-radius:50%;background:none;cursor:pointer}
.courses input[type=color]::-webkit-color-swatch-wrapper{padding:0}
.courses input[type=color]::-webkit-color-swatch{border:1px solid rgba(255,255,255,.6);border-radius:50%}
.cc{grid-area:code;font-size:1rem;font-weight:700;color:var(--g-t1)!important;white-space:nowrap}
.nick{grid-area:nick;padding:8px 10px}
.reset{grid-area:reset}
.reset:disabled{opacity:.5;cursor:default;text-decoration:none}
.courses .warn{grid-area:warn;font-size:.85rem;color:#FFC2B8;margin-top:2px}.courses .warn:empty{display:none}
#toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,10px);max-width:calc(100vw - 32px);padding:10px 18px;border-radius:8px;
 background:rgba(30,35,46,.88);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);outline:1px solid rgba(255,255,255,.5);
 color:#fff;font-weight:600;opacity:0;pointer-events:none;transition:opacity .2s ease-out,transform .2s ease-out}
#toast.show{opacity:1;transform:translate(-50%,0)}

/* narrower windows: two columns, then one (the site's own breakpoints) */
@media (max-width:1150px){
.wrap{grid-template-columns:repeat(2,minmax(0,1fr))}
.actions{grid-column:1/-1;grid-row:3;justify-self:center}
.today{grid-column:1/-1;grid-row:4}.nx.exam{grid-column:1;grid-row:5}.nx.quiz{grid-column:2;grid-row:5}
.bands{grid-row:6}.band:nth-child(3){grid-column:1/-1}.bins{grid-row:7}}
@media (max-width:768px){
.wrap{grid-template-columns:minmax(0,1fr);margin:20px 10px;width:auto;padding:20px 15px}
h1{font-size:2.25rem}
.today,.nx.exam,.nx.quiz,.band:nth-child(3){grid-column:1}.nx.exam{grid-row:5}.nx.quiz{grid-row:6}.bands{grid-row:7}.bins{grid-row:8}
.sheet{padding:18px}.field-row{grid-template-columns:1fr}
.courses li{grid-template-columns:32px 1fr auto;grid-template-areas:"color code reset" ". nick nick" ". warn warn";row-gap:6px}}
.no-anim *{transition:none!important}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}.row:hover{transform:none}}
"""
