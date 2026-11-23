# Registry: skills, plugins and agents for apps built with Project Kit

This folder is the source of truth for the AI jobs that apps built with Project Kit run at
runtime. It is **not** part of the Project Kit plugin itself: the plugin's own skills live in
`skills/` and are what Claude Code loads. Nothing here is loaded by `claude plugin install`.

The first app to use it is **PANKRA** (design: `apps/pankra/` on the `app/pankra-design`
branch). Any later app can add its own nodes beside these.

## Layout

```
registry/
  index.json                 generated: every node, its version, path and edges
  schema/node.schema.json    the shape of every node.json
  build_index.py             validates the nodes and writes index.json (--check in CI)
  skills/<name>/SKILL.md     instructions, Claude-skill compatible (name + description frontmatter)
  skills/<name>/node.json    provider-agnostic metadata the app needs to run the skill
  agents/<name>/AGENT.md     what the agent does, in order
  agents/<name>/node.json    its steps (skills, in order) and requirements
  plugins/<name>/node.json   a bundle: which skills, agents and tools ship together
```

## Node kinds

| Kind | Is | Runs |
|---|---|---|
| `skill` | One job: instructions, an input schema, an output schema | One LLM call (or a short tool loop) on the chosen provider |
| `agent` | An ordered list of skills; each step's output feeds the next | Several skill runs, one provider for all steps |
| `plugin` | A bundle of skills, agents and the app tools they may call | Nothing by itself; it is what an app installs |

Every `node.json` says which providers the node runs on (`claude`, `gpt`; more later), the
default model per provider, what it `requires` before a run (`apiKey`, `stravaToken`,
`spotifyToken`), and whether it needs image input (`vision`). The app reads this to ask for the
right credential before running, so a node always knows which LLM it is being run through.

Model names go stale. They are defaults only; the app lets the user pick another.

## How an app pulls the registry by itself

1. The app is configured with `REGISTRY_REPO=miricoder/project-kit` and `REGISTRY_REF`
   (a branch or a tag; `main` once this is merged).
2. On every deploy, every 6 hours and on "Sync now", it fetches
   `https://raw.githubusercontent.com/<REGISTRY_REPO>/<REGISTRY_REF>/registry/index.json`.
3. For each node whose `version` differs from the one it holds, it fetches the node's files
   (paths are in the index), validates `node.json` against `schema/node.schema.json`, and
   saves it as a new version. The old version is kept so a run can be repeated exactly.
4. Edges in the index (`contains`, `calls`, `uses`) become the app's graph view.
5. A node removed from the index is marked retired, never deleted, because past runs refer
   to it.

No credentials are needed to pull: the repository is public. Pin `REGISTRY_REF` to a tag for
a release so a registry change cannot change a live app without a deploy.

## Adding or changing a node

1. Add or edit the folder. Bump `version` in its `node.json` (semver) on any change to the
   instructions or schemas.
2. Run `python3 registry/build_index.py` to validate and regenerate `index.json`.
3. Commit both. CI runs `python3 registry/build_index.py --check` through the unit tests and
   fails if `index.json` is stale or a node is invalid.

## Porting a skill made in Claude

A Claude skill's `SKILL.md` drops in as it is. Add a `node.json` beside it. Where the skill
names a Claude-only tool (Docs, Sheets, project files), say what the app tool is instead,
and list it under `tools` in `node.json`.
