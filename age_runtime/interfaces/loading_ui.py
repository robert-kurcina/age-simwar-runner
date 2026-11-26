"""Shared browser loading presentation, independent of a frontend framework."""
from html import escape

CSS = """
.age-load-panel{position:relative;min-height:180px}
.age-load-state{display:flex;align-items:center;gap:10px;padding:12px 0;color:#50616d}
.age-load-state[hidden],.age-skeleton[hidden]{display:none}
.age-spinner{width:24px;height:24px;flex:none;animation:age-spin .9s linear infinite}
.age-load-state:not([data-state="loading"]) .age-spinner{display:none}
.age-skeleton{position:absolute;inset:0;display:grid;align-content:center;gap:12px;padding:24px;background:#eef1f3;pointer-events:none;z-index:450}
.age-skeleton span{display:block;height:12px;border-radius:5px;background:#d3dce1;animation:age-pulse 1.5s ease-in-out infinite}
.age-skeleton span:nth-child(2){width:72%}
.age-skeleton span:nth-child(3){width:46%}
@keyframes age-spin{to{transform:rotate(360deg)}}
@keyframes age-pulse{50%{opacity:.45}}
@media(prefers-reduced-motion:reduce){.age-spinner,.age-skeleton span{animation:none}}
"""

SPINNER = """<svg class="age-spinner" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" opacity=".2" stroke-width="2.5"/>
<path d="M12 3a9 9 0 0 1 9 9" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
</svg>"""


def status_markup(prefix):
    key = escape(prefix, quote=True)
    return (f'<div id="{key}-status" class="age-load-state" data-state="idle" hidden>'
            + SPINNER + f'<span id="{key}-message" role="status" aria-live="polite"></span></div>')


def skeleton_markup(prefix):
    return f'<div id="{escape(prefix, quote=True)}-skeleton" class="age-skeleton" aria-hidden="true" hidden><span></span><span></span><span></span></div>'

JS = """
function ageLoading(prefix, target, state, message, placeholder=false) {
 const box=document.getElementById(prefix+'-status');
 const text=document.getElementById(prefix+'-message');
 const skeleton=document.getElementById(prefix+'-skeleton');
 box.dataset.state=state;
 box.hidden=state==='idle';
 text.textContent=message;
 target.setAttribute('aria-busy',String(state==='loading'));
 if(skeleton) skeleton.hidden=!(state==='loading' && placeholder);
}
"""
