---
name: graph
description: Show Project Kit as a graph — every skill, each project's phases, gates, artifacts and build slices as nodes and relationships, stored in a local database and viewable in any browser (phone included) without Claude. Also exports Cypher for Neo4j. Use when the user says /graph, "show my skills", "show the pipeline as a graph", "graph view", "open the graph", "export to Neo4j", or asks which skills are missing.
---

# /graph

Project Kit's pipeline as a property graph, in the style of a graph-database browser:
labelled nodes (`:Skill`, `:Project`, `:Phase`, `:Gate`, `:Artifact`, `:Slice`) and typed
relationships (`RUNS`, `NEXT`, `WRITES`, `GUARDS`, `BUILDS`, `ROUTES_TO`, …). Phases with no
skill behind them show as red dashed `:Skill:Missing` nodes.

The graph lives in a SQLite database (`~/.claude/project-kit/graph.db`) that `pk graph`
rebuilds from the skills' `SKILL.md` files, each project's `pipeline.json` and its
`docs/backlog.md`. It is a cache, never the source of truth: deleting it loses nothing.

## Commands

Resolve the launcher once, as every Project Kit skill does:

```bash
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

| Command | What it does |
|---|---|
| `pk graph -C . sync` | rebuild from the skills and the project in this directory |
| `pk graph sync --all` | … and every project in the Project Kit registry |
| `pk graph show` | node and relationship counts, and which skills are missing |
| `pk graph -C . serve` | the interactive viewer at http://127.0.0.1:7474, live: every page load re-syncs |
| `pk graph -C . serve --host 0.0.0.0` | the same, reachable from a phone on the same network |
| `pk graph -C . html -o graph.html` | one standalone page with the graph inside, to open or send anywhere |
| `pk graph -C . export -o graph.cypher` | Cypher for Neo4j (`--format json` for raw JSON) |

## Step 1: Sync and summarise

```bash
pk graph -C . sync
pk graph show
```

Outside a project (no `pipeline.json`) `sync` still records the plugin's skills. Report in
one short block: nodes per label, which skills are missing, and each project's current
phase. A non-zero exit lists projects that could not be read; pass the reasons on.

## Step 2: Give the user a way to look at it

Ask which they want, unless they already said:

- **Live, on this computer:** start `pk graph -C . serve` in the background and give them
  http://127.0.0.1:7474. It stays current while they work: the page re-syncs on load and
  has a Refresh button.
- **On their phone:** `serve --host 0.0.0.0`, then the computer's local network address
  (e.g. `http://192.168.1.20:7474`). Say that anyone on the same network can open it while
  it runs, and to stop it with Ctrl+C when done.
- **A file:** `pk graph -C . html -o docs/graph.html`. It opens in any browser with no
  server; it shows the graph as of now, so regenerate it after the pipeline moves.
- **Neo4j:** `pk graph -C . export -o graph.cypher`, then load it into their own Neo4j:

  ```bash
  cypher-shell -a neo4j+s://<instance>.databases.neo4j.io -u neo4j -p '<password>' -f graph.cypher
  ```

  Every node carries the label `PkNode` and a unique `pk_id`, and the statements `MERGE`,
  so re-running the export after a sync updates the graph in place. In Neo4j Browser:
  `MATCH (n:PkNode)-[r]->(m:PkNode) RETURN n, r, m`. Never ask for the password in chat; the
  user runs that command themselves.

## Rules

- The graph only reports. It never changes a phase, gate or slice; `pk state` and
  `pk slice` do that.
- `serve --host 0.0.0.0` exposes project names and paths to the local network. Use it only
  when the user asks to view on another device, and say so.
- A standalone HTML file contains the project's paths and names. Do not commit or publish
  it to a public place without asking.
