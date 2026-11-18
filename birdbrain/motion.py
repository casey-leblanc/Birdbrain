"""How Birdbrain moves: one small vocabulary, in one place.

Everything on the page that moves takes its timing from the variables below, so the whole app speeds up, slows down
or goes still together:

    --m-fast   120ms   a press, a hover, a chip appearing
    --m-base   200ms   a sheet opening, a card settling
    --m-slow   320ms   a card travelling, the list making room
    --m-long   560ms   arriving on the page
    --m-out    easing for things arriving (fast, then gentle)
    --m-in     easing for things leaving
    --m-move   easing for things going from one place to another
    --m-spring a spring with a little overshoot, for things let go of; its time is --m-spring-time

Only transform and opacity are ever animated, so nothing is laid out again mid-flight, and every animation can be cut
short by the next input.

Three levels, chosen in Settings > Look and kept as the "motion" preference:

    full     everything, including the ripple of light and the sheen on the glass
    subtle   the movement that explains what happened, without the ripple and sheen
    off      nothing moves; every change is instant

With no choice made, the level is "off" if the system asks for reduced motion and "full" otherwise. The page's root
element carries the level in force as data-motion.
"""
from __future__ import annotations

import math

LEVELS = ("full", "subtle", "off")
LEVEL_NAMES = {"full": "Full", "subtle": "Subtle", "off": "Off"}
LEVEL_HINTS = {"full": "Everything moves, with ripples of light on the glass.",
               "subtle": "Cards still move to show what happened. No ripples or sheen.",
               "off": "Nothing moves. Every change is instant."}

# Sets data-motion on the root element before the first paint: the saved choice, or the system's wish.
HEAD_JS = ("(function(){var r=document.documentElement,p=r.dataset.motionPref;"
           "r.dataset.motion=p||(matchMedia('(prefers-reduced-motion: reduce)').matches?'off':'full');})();")


def spring(damping: float = 0.68, points: int = 22) -> str:
    """A damped spring from 0 to 1, as a CSS linear() easing: it runs a little past 1 and settles. `damping` under
    1 gives the overshoot (0.68 is about 5%). Sampled over the time it takes to come to rest."""
    omega = 1.0
    damped = omega * math.sqrt(1 - damping * damping)
    settle = 6.2 / (damping * omega)   # e^(-6.2) is under 0.3%: at rest, to the eye
    stops = []
    for n in range(points + 1):
        t = settle * n / points
        x = 1 - math.exp(-damping * omega * t) * (math.cos(damped * t) + damping * omega / damped * math.sin(damped * t))
        stops.append(f"{0 if n == 0 else 1 if n == points else round(x, 3):g}")
    return "linear(" + ",".join(stops) + ")"


TOKENS_CSS = f"""
/* motion: the one vocabulary (motion.py) */
:root{{--m-fast:120ms;--m-base:200ms;--m-slow:320ms;--m-long:560ms;--m-spring-time:480ms;
 --m-out:cubic-bezier(.16,1,.3,1);--m-in:cubic-bezier(.4,0,1,1);--m-move:cubic-bezier(.2,0,0,1);
 --m-spring:cubic-bezier(.3,1.35,.5,1)}}
/* a real spring where the browser can draw one (the line above is the stand-in where it can't) */
@supports (transition-timing-function:linear(0,1)){{:root{{--m-spring:{spring()}}}}}
:root[data-motion=off]{{--m-fast:0ms;--m-base:0ms;--m-slow:0ms;--m-long:0ms;--m-spring-time:0ms}}
:root[data-motion=off] *,:root[data-motion=off] *::before,:root[data-motion=off] *::after{{transition:none!important;animation:none!important}}
"""

# For every script on the page: CALM.matches is true when nothing should move; MS and EASE are the timings above, read
# from the stylesheet so script and styles keep the same pace. readMotion() reads them again after the level changes.
SCRIPT = ("var CALM={get matches(){return document.documentElement.dataset.motion==='off';}},MS={},EASE={};"
          "function readMotion(){var cs=getComputedStyle(document.documentElement);"
          "['fast','base','slow','long'].forEach(function(k){MS[k]=parseFloat(cs.getPropertyValue('--m-'+k))||0;});"
          "MS.spring=parseFloat(cs.getPropertyValue('--m-spring-time'))||0;"
          "['out','in','move','spring'].forEach(function(k){EASE[k]=cs.getPropertyValue('--m-'+k).trim()||'ease';});}"
          "readMotion();")
