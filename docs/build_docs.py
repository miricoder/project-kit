#!/usr/bin/env python3
"""Generate the Project Kit documentation pages.

Everything is read from the real sources, so the docs cannot drift from the plugin:

  .claude-plugin/plugin.json                     name and version
  skills/*/SKILL.md                              skill names and descriptions
  skills/pipeline/references/phases.md           the phase table
  ~/.claude/project-kit/registry.json            project status rows

    python3 docs/build_docs.py            # write docs/*.html
    python3 docs/build_docs.py --check    # fail if the committed pages are stale

Colours are the validated reference status palette, used unchanged. Status is always
icon + label as well as colour, so colour never carries meaning on its own.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
SKILLS = ROOT / "skills"
PHASES_MD = SKILLS / "pipeline" / "references" / "phases.md"

WAVE1 = ("ideate", "proposal", "design", "handover", "verdict")
CHECKPOINTS = ("ideate", "proposal", "handover", "verdict")

# Status roles -> (label, icon). The icon is the mitigation that lets these colours be
# used on a light surface where warning and serious sit below 3:1 by design.
STATUS = {
    "complete":    ("good", "✔"),
    "in progress": ("warning", "◐"),
    "blocked":     ("critical", "■"),
    "not started": ("idle", "○"),
}
RULING_STATUS = {
    "SOUND": "good", "FIX FIRST": "warning", "NEEDS INFO": "serious",
    "SPLIT": "serious", "REJECT": "critical",
}

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_TICKS = re.compile(r"`([^`]+)`")


def md_inline(text: str) -> str:
    """Escape, then turn `code` spans into <code>. Table cells come from markdown."""
    return _TICKS.sub(r"<code>\1</code>", html.escape(text))


# --------------------------------------------------------------------------- sources

def frontmatter(path: Path) -> Dict[str, str]:
    match = _FRONTMATTER.match(path.read_text())
    if not match:
        return {}
    fields: Dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key:
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def read_phases() -> List[Dict[str, str]]:
    """Parse the phase table out of phases.md: | # | Phase | Skill | Reads | Writes | Gate |"""
    rows: List[Dict[str, str]] = []
    for line in PHASES_MD.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not cells[0].isdigit():
            continue
        rows.append({
            "n": cells[0],
            "phase": cells[1],
            "skill": cells[2].strip("`/"),
            "reads": cells[3],
            "writes": cells[4],
            "gate": "" if cells[5] in ("—", "-") else cells[5].strip("*"),
        })
    return rows


def read_skills() -> Dict[str, str]:
    return {p.parent.name: frontmatter(p).get("description", "")
            for p in sorted(SKILLS.glob("*/SKILL.md"))}


def read_registry() -> List[Dict[str, Any]]:
    path = Path(os.path.expanduser(
        os.environ.get("PROJECT_KIT_REGISTRY", "~/.claude/project-kit/registry.json")))
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text()).get("projects", [])
    except json.JSONDecodeError:
        return []


# --------------------------------------------------------------------------- shell

def css() -> str:
    return """
:root{
  color-scheme:light;
  --plane:#f9f9f7; --surface:#fcfcfb;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --rule:#c3c2b7; --ring:rgba(11,11,11,.10);
  --accent:#2a78d6;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b; --idle:#898781;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])){
    color-scheme:dark;
    --plane:#0d0d0d; --surface:#1a1a19;
    --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --rule:#383835; --ring:rgba(255,255,255,.10);
    --accent:#3987e5;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#1a1a19;
  --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --rule:#383835; --ring:rgba(255,255,255,.10);
  --accent:#3987e5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-text-size-adjust:100%}
.wrap{max-width:1040px;margin:0 auto;padding:28px 20px 72px}
header.top{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;
  justify-content:space-between;border-bottom:1px solid var(--grid);padding-bottom:16px}
h1{font-size:25px;margin:0;letter-spacing:-.01em}
h2{font-size:19px;margin:40px 0 12px;letter-spacing:-.01em}
h3{font-size:15px;margin:24px 0 8px}
p{color:var(--ink-2);margin:10px 0}
a{color:var(--accent)}
.ver{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
nav.pages{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 0}
nav.pages a{display:inline-block;padding:6px 12px;border:1px solid var(--ring);
  border-radius:999px;text-decoration:none;font-size:13px;background:var(--surface)}
nav.pages a[aria-current="page"]{border-color:var(--accent);color:var(--accent);font-weight:600}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:16px}
.grid{display:grid;gap:12px}
@media(min-width:720px){.cols-2{grid-template-columns:1fr 1fr}}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:560px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--grid);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  font-weight:600;white-space:nowrap}
td.num,th.num{font-variant-numeric:tabular-nums}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
code{font-size:.9em;background:var(--surface);border:1px solid var(--ring);
  border-radius:4px;padding:.1em .35em}
pre{background:var(--surface);border:1px solid var(--ring);border-radius:8px;
  padding:12px 14px;overflow-x:auto;font-size:12.5px;line-height:1.55}
pre code{border:0;background:none;padding:0}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;
  white-space:nowrap}
.badge .dot{width:9px;height:9px;border-radius:2px;flex:none}
.s-good .dot{background:var(--good)} .s-warning .dot{background:var(--warning)}
.s-serious .dot{background:var(--serious)} .s-critical .dot{background:var(--critical)}
.s-idle .dot{background:var(--idle)}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0 0;padding:0;list-style:none}
.tiles{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}
.tile .k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  font-weight:600}
.tile .v{font-size:30px;line-height:1.15;margin-top:4px;letter-spacing:-.02em}
.steps{display:flex;gap:2px;min-width:132px}
.steps i{height:8px;flex:1;border-radius:1px;background:var(--grid)}
.steps i.done{background:var(--good)} .steps i.now{background:var(--warning)}
.steps i.stop{background:var(--critical)}
.muted{color:var(--muted);font-size:12.5px}
.gate{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;
  text-transform:uppercase;color:var(--critical);border:1px solid var(--critical);
  border-radius:4px;padding:1px 5px}
figure{margin:14px 0}
figcaption{font-size:12.5px;color:var(--muted);margin-top:8px}
svg{max-width:100%;height:auto;display:block}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--grid);
  font-size:12.5px;color:var(--muted)}
"""


def page(title: str, current: str, version: str, body: str) -> str:
    nav = ""
    for href, label in (("index.html", "Pipeline"), ("project_kit_know_how.html", "Know-how & projects")):
        mark = ' aria-current="page"' if href == current else ""
        nav += f'<a href="{href}"{mark}>{html.escape(label)}</a>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{html.escape(title)}</title>
<style>{css()}</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <h1>Project Kit</h1>
  <span class="ver">v{html.escape(version)} &middot; generated</span>
</header>
<nav class="pages">{nav}</nav>
{body}
<footer>
  Generated by <code>docs/build_docs.py</code> from the plugin's own manifests and skill
  frontmatter &mdash; <a href="https://github.com/miricoder/project-kit">miricoder/project-kit</a>
</footer>
</div>
</body>
</html>
"""


def badge(label: str, role: str, icon: str) -> str:
    return (f'<span class="badge s-{role}"><span class="dot" aria-hidden="true"></span>'
            f'{icon} {html.escape(label)}</span>')


def status_badge(status: str) -> str:
    role, icon = STATUS.get(status, ("idle", "○"))
    return badge(status, role, icon)


def status_legend() -> str:
    items = "".join(f"<li>{status_badge(s)}</li>" for s in STATUS)
    return f'<ul class="legend">{items}</ul>'


# --------------------------------------------------------------------------- diagram

def flow_svg() -> str:
    """Wave 1 left to right, the back-propagation arc, then the judge gate."""
    nodes = [("ideate", 40), ("proposal", 196), ("design", 352), ("handover", 508), ("verdict", 664)]
    parts = [
        '<svg viewBox="0 0 880 178" role="img" '
        'aria-label="Pipeline flow: ideate to proposal to design to handover to verdict, '
        'which back-propagates to earlier phases or passes the judge gate into the build phases.">',
        '<defs><marker id="pk-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>',
        '<g fill="none" stroke="currentColor" stroke-width="2" color="var(--rule)" '
        'marker-end="url(#pk-arrow)">',
    ]
    for _, x in nodes[:-1]:
        parts.append(f'<path d="M{x + 132} 60 H{x + 160}"/>')
    parts.append('<path d="M708 94 V140 H120 V84"/>')          # back-propagate
    parts.append('<path d="M772 60 H812 V60"/>')                 # verdict -> gate
    parts.append("</g>")
    for name, x in nodes:
        checkpoint = name in CHECKPOINTS
        parts.append(
            f'<g><rect x="{x}" y="38" width="132" height="44" rx="8" fill="var(--surface)" '
            f'stroke="{"var(--accent)" if checkpoint else "var(--rule)"}" stroke-width="1.5"/>'
            f'<text x="{x + 66}" y="65" text-anchor="middle" font-size="14" font-weight="600" '
            f'font-family="system-ui,sans-serif" fill="var(--ink)">/{name}</text></g>')
        if checkpoint:
            parts.append(
                f'<text x="{x + 66}" y="27" text-anchor="middle" font-size="10.5" '
                f'font-family="system-ui,sans-serif" fill="var(--accent)" '
                f'font-weight="600">checkpoint</text>')
    parts.append('<text x="414" y="163" text-anchor="middle" font-size="11.5" '
                 'font-family="system-ui,sans-serif" fill="var(--muted)">'
                 'back-propagate &mdash; bounded by a max-round limit</text>')
    parts.append('<g><rect x="812" y="38" width="56" height="44" rx="8" fill="var(--surface)" '
                 'stroke="var(--critical)" stroke-width="1.5"/>'
                 '<text x="840" y="59" text-anchor="middle" font-size="10" font-weight="700" '
                 'font-family="system-ui,sans-serif" fill="var(--critical)">JUDGE</text>'
                 '<text x="840" y="71" text-anchor="middle" font-size="10" font-weight="700" '
                 'font-family="system-ui,sans-serif" fill="var(--critical)">GATE</text></g>')
    parts.append('<text x="840" y="100" text-anchor="middle" font-size="11" '
                 'font-family="system-ui,sans-serif" fill="var(--muted)">to build</text>')
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- pages

def modes_table() -> str:
    rows = [
        ("manual", "Stops after <strong>every</strong> phase and offers a menu", "every phase"),
        ("auto <span class='muted'>(default)</span>",
         "Advances between phases, stopping at the four checkpoints", "4 checkpoints"),
        ("yolo", "End to end with no pipeline stops, subject to the budget cap", "none"),
    ]
    body = "".join(f"<tr><td><code>{m}</code></td><td>{d}</td><td>{s}</td></tr>"
                   for m, d, s in rows)
    return ('<div class="scroll"><table><thead><tr><th>Mode</th><th>Behaviour</th>'
            f'<th>Stops</th></tr></thead><tbody>{body}</tbody></table></div>')


def build_index(version: str, phases: List[Dict[str, str]], skills: Dict[str, str]) -> str:
    built = {p["phase"] for p in phases if p["phase"] in skills}

    cards = []
    if "pipeline" in skills:
        cards.append(f"""<div class="card">
  <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline">
    <h3 style="margin:0"><code>/pipeline</code></h3>{badge("shipped", "good", "\u2714")}</div>
  <p style="margin:8px 0 10px"><strong>The conductor &mdash; not a phase.</strong>
  {html.escape(skills["pipeline"])}</p>
  <div class="muted"><strong>Reads &amp; writes</strong>
  <code>pipeline.json</code>, <code>~/.claude/project-kit/registry.json</code></div>
</div>""")
    for p in phases:
        name = p["phase"]
        shipped = name in skills
        desc = skills.get(name, "Declared in pipeline state; its skill has not shipped yet.")
        gate = f'<span class="gate">{html.escape(p["gate"])} gate</span> ' if p["gate"] else ""
        chip = badge("shipped", "good", "✔") if shipped else badge("planned", "idle", "○")
        cards.append(f"""<div class="card">
  <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline">
    <h3 style="margin:0"><code>/{html.escape(name)}</code></h3>{chip}</div>
  <p style="margin:8px 0 10px">{gate}{html.escape(desc)}</p>
  <div class="muted"><strong>Reads</strong> {md_inline(p["reads"])}<br>
  <strong>Writes</strong> {md_inline(p["writes"])}</div>
</div>""")

    matrix_rows = "".join(
        f'<tr><td class="num">{p["n"]}</td><td><code>/{html.escape(p["phase"])}</code></td>'
        f'<td>{md_inline(p["reads"])}</td><td>{md_inline(p["writes"])}</td>'
        f'<td>{("<span class=gate>" + html.escape(p["gate"]) + "</span>") if p["gate"] else "<span class=muted>&mdash;</span>"}</td>'
        f'<td>{status_badge("complete") if p["phase"] in built else status_badge("not started")}</td></tr>'
        for p in phases)

    body = f"""
<h2>The pipeline</h2>
<p>Eleven phases, each owned by one skill. A phase hands off to the next only after
recording what it produced; the next skill reads that record and <strong>refuses</strong> if a
precondition is unmet. Gates are decided by scripts, never asserted by a model.</p>
<figure>{flow_svg()}
<figcaption>Wave 1. Checkpoint phases pause for you in <code>auto</code> mode.
<code>/verdict</code> either back-propagates for another round or passes the judge gate,
which <code>/initiate</code> cannot start without.</figcaption></figure>

<h2>Skills</h2>
<div class="grid cols-2">{"".join(cards)}</div>

<h2>How phases interact</h2>
<p>Each row is a phase: what it consumes, what it produces, and the gate that guards it.
Artifacts are the contract between phases &mdash; a missing artifact is why a skill refuses.</p>
<div class="scroll"><table>
<thead><tr><th class="num">#</th><th>Phase</th><th>Reads</th><th>Writes</th><th>Gate before</th><th>Status</th></tr></thead>
<tbody>{matrix_rows}</tbody></table></div>
{status_legend()}

<h2>Run modes</h2>
{modes_table()}
<p>The four <code>auto</code> checkpoints: after <code>/ideate</code> (is this the idea?),
after <code>/proposal</code> (accept scope and cost?), before the judge panel runs (this
spends API credit), and after <code>/verdict</code> (accept the ruling, or revise?).</p>
<p><strong>The budget cap is not a checkpoint.</strong> It halts the run in every mode,
including <code>yolo</code>.</p>
"""
    return page("Project Kit — pipeline", "index.html", version, body)


def build_knowhow(version: str, phases: List[Dict[str, str]],
                  projects: List[Dict[str, Any]]) -> str:
    order = [p["phase"] for p in phases]

    def steps(reached: Optional[str]) -> str:
        cells = []
        index = order.index(reached) if reached in order else len(order)
        for i, _ in enumerate(order):
            cls = "done" if i < index else ("now" if i == index else "")
            cells.append(f'<i class="{cls}"></i>')
        return f'<span class="steps" aria-hidden="true">{"".join(cells)}</span>'

    if projects:
        rows = []
        for row in projects:
            ruling = row.get("judge_ruling")
            ruling_cell = (badge(ruling, RULING_STATUS.get(ruling, "idle"), "◆")
                           if ruling else '<span class="muted">&mdash;</span>')
            launched = (badge("launched", "good", "✔") if row.get("launched")
                        else '<span class="muted">not yet</span>')
            phase = row.get("phase", "—")
            rows.append(
                f'<tr><td><strong>{html.escape(str(row.get("project", "?")))}</strong>'
                f'<div class="muted">{html.escape(str(row.get("path", "")))}</div></td>'
                f'<td>{steps(phase)}<div class="muted">{html.escape(str(phase))}</div></td>'
                f'<td><code>{html.escape(str(row.get("mode", "")))}</code></td>'
                f'<td>{ruling_cell}</td><td>{launched}</td>'
                f'<td class="num muted">{html.escape(str(row.get("updated_at", ""))[:10])}</td></tr>')
        table = ('<div class="scroll"><table><thead><tr><th>Project</th><th>Phase reached</th>'
                 '<th>Mode</th><th>Judge ruling</th><th>Launch</th><th class="num">Updated</th>'
                 f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{status_legend()}')
        total = len(projects)
        judged = sum(1 for p in projects if p.get("judge_ruling"))
        launched_n = sum(1 for p in projects if p.get("launched"))
        active = total - launched_n
    else:
        table = ('<div class="card"><p style="margin:0">No projects yet. Run '
                 '<code>/ideate &lt;your idea&gt;</code> in a project directory and this table '
                 'fills itself from <code>~/.claude/project-kit/registry.json</code>.</p></div>')
        total = judged = launched_n = active = 0

    tiles = "".join(
        f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div></div>'
        for k, v in (("Projects", total), ("In flight", active),
                     ("Judged", judged), ("Launched", launched_n)))

    body = f"""
<h2>Projects</h2>
<p>Read from your own registry at <code>~/.claude/project-kit/registry.json</code>. Project
data is deliberately never committed to this repo &mdash; the repo is the tool.</p>
<div class="tiles">{tiles}</div>
<h3>Status</h3>
{table}

<h2>Install</h2>
<pre><code>claude plugin marketplace add miricoder/project-kit
claude plugin install project-kit</code></pre>
<p>Then <code>/reload-plugins</code>, or start a new session. Verify with
<code>claude plugin details project-kit</code>; update later with
<code>claude plugin update project-kit</code>.</p>
<p><strong>Requires Claude Code 2.x or newer</strong> &mdash; plugin support. Check
<code>claude --version</code>; upgrade with
<code>npm i -g @anthropic-ai/claude-code@latest</code>.</p>

<h2>Using it</h2>
<pre><code>/ideate I want an app that tracks my houseplants
/pipeline                 # where are we, what runs next
/pipeline mode yolo       # manual | auto | yolo
/pipeline run --to design</code></pre>
{modes_table()}

<h2>Two layers of autonomy</h2>
<p><code>yolo</code> removes Project Kit's checkpoints. It <strong>cannot</strong> remove
Claude Code's own tool-permission prompts &mdash; those are harness-level and no plugin can
suppress them. For a genuinely unattended run, allowlist them too:</p>
<pre><code>// ~/.claude/settings.json
{{
  "permissions": {{
    "allow": ["Bash(python3:*)", "Bash(git:*)", "Bash(gh:*)", "Edit", "Write"]
  }}
}}</code></pre>
<p><code>/pipeline mode yolo</code> reports whether this is configured, so the mode never
<em>looks</em> hands-off while silently waiting on a prompt.</p>

<h2>Budget</h2>
<p>Every project carries <code>budget.max_usd</code> in its <code>pipeline.json</code>.
<code>yolo</code> adds no confirmation stops but still halts when spend passes the ceiling &mdash;
what that rules out is an unattended <code>REJECT</code> &rarr; re-judge &rarr;
<code>REJECT</code> loop burning credit with nobody watching.</p>

<h2>The judge panel</h2>
<p>The judge gate needs <strong>three verdicts from three different model families</strong>.
Two rules are enforced in code, not left to judgement:</p>
<ol>
<li><strong>No family may hold two seats.</strong> Two judges from one family share priors,
producing a ruling that looks independent and is not.</li>
<li><strong>The authoring family is excluded.</strong> Claude writes the plan, so Anthropic
cannot judge it.</li>
</ol>
<div class="scroll"><table>
<thead><tr><th>Transport</th><th>When</th></tr></thead>
<tbody>
<tr><td><code>api_key</code></td><td>A real API key exists. Fully automated</td></tr>
<tr><td><code>cli</code></td><td>A subscription-backed CLI &mdash; e.g.
  <code>npm i -g @openai/codex</code> reuses an existing ChatGPT login, no API key and no
  extra cost</td></tr>
<tr><td><code>paste</code></td><td>Neither. The brief is rendered for you to paste, and the
  returned JSON is validated before being accepted</td></tr>
</tbody></table></div>
<p>A ChatGPT subscription is <strong>not</strong> an OpenAI API key. Using
<code>api_key</code> for that seat means paying for API usage separately;
<code>cli</code> avoids it.</p>

<h2>Where your data lives</h2>
<div class="scroll"><table>
<thead><tr><th>What</th><th>Where</th></tr></thead>
<tbody>
<tr><td>Per-project phase state, gates, mode, budget</td><td><code>&lt;project&gt;/pipeline.json</code></td></tr>
<tr><td>Human-readable project snapshot</td><td><code>&lt;project&gt;/.github/projects/&lt;name&gt;.md</code></td></tr>
<tr><td>Registry of all projects, for the table above</td><td><code>~/.claude/project-kit/registry.json</code></td></tr>
</tbody></table></div>
"""
    return page("Project Kit — know-how & projects", "project_kit_know_how.html", version, body)


# --------------------------------------------------------------------------- main

def render() -> Dict[Path, str]:
    version = json.loads(PLUGIN.read_text())["version"]
    phases = read_phases()
    skills = read_skills()
    projects = read_registry()
    return {
        DOCS / "index.html": build_index(version, phases, skills),
        DOCS / "project_kit_know_how.html": build_knowhow(version, phases, projects),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="build_docs.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the committed pages differ from a fresh render")
    args = parser.parse_args(argv)

    pages = render()
    if args.check:
        stale = [p.name for p, text in pages.items()
                 if not p.exists() or p.read_text() != text]
        if stale:
            print("stale docs (run python3 docs/build_docs.py): " + ", ".join(stale),
                  file=sys.stderr)
            return 1
        print("docs are up to date")
        return 0
    for path, text in pages.items():
        path.write_text(text)
        print(f"wrote {path.relative_to(ROOT)} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
