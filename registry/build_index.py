#!/usr/bin/env python3
"""Validate the registry's nodes and write registry/index.json.

Apps built with Project Kit pull index.json to find every skill, agent and plugin, its
version and its files. This script is the only thing that writes it, so the index can never
disagree with the folders.

    python3 registry/build_index.py           validate and write index.json
    python3 registry/build_index.py --check   validate; exit 1 if index.json is stale

Exit codes: 0 ok, 1 invalid node or stale index, 2 usage error. Pure standard library.
The checks below mirror schema/node.schema.json; keep the two in step.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REGISTRY = Path(__file__).resolve().parent
INDEX = REGISTRY / "index.json"
KIND_DIRS = {"skill": "skills", "agent": "agents", "plugin": "plugins"}
DOC_FILE = {"skill": "SKILL.md", "agent": "AGENT.md"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PROVIDERS = {"claude", "gpt"}
REQUIREMENTS = {"apiKey", "stravaToken", "spotifyToken"}
REQUIRED = {
    "skill": ("providers", "requires", "vision", "tools", "input", "output"),
    "agent": ("providers", "requires", "steps"),
    "plugin": ("skills", "agents", "tools"),
}


def frontmatter(path: Path) -> Dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    block = text[4:text.find("\n---", 4)]
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def check_node(kind: str, folder: Path, node: dict) -> List[str]:
    where = f"{KIND_DIRS[kind]}/{folder.name}"
    errors = []
    for key in ("kind", "name", "version", "description", "apps") + REQUIRED[kind]:
        if key not in node:
            errors.append(f"{where}: missing '{key}'")
    if errors:
        return errors
    if node["kind"] != kind:
        errors.append(f"{where}: kind is '{node['kind']}', folder says '{kind}'")
    if node["name"] != folder.name:
        errors.append(f"{where}: name '{node['name']}' must match the folder name")
    if not NAME_RE.match(node["name"]):
        errors.append(f"{where}: name must be lower-case letters, digits and hyphens")
    if not VERSION_RE.match(node["version"]):
        errors.append(f"{where}: version must be MAJOR.MINOR.PATCH")
    if len(node["description"]) < 20:
        errors.append(f"{where}: description is too short to tell a user what it does")
    if not node["apps"]:
        errors.append(f"{where}: apps must name at least one app")
    if kind in ("skill", "agent"):
        providers = node["providers"]
        if not providers or set(providers) - PROVIDERS:
            errors.append(f"{where}: providers must be a non-empty subset of {sorted(PROVIDERS)}")
        for provider, spec in providers.items():
            if not isinstance(spec, dict) or not spec.get("model"):
                errors.append(f"{where}: provider '{provider}' needs a default model")
        unknown = set(node["requires"]) - REQUIREMENTS
        if unknown:
            errors.append(f"{where}: unknown requirements {sorted(unknown)}")
        if "apiKey" not in node["requires"]:
            errors.append(f"{where}: every LLM node requires 'apiKey'")
        doc = folder / DOC_FILE[kind]
        if not doc.is_file():
            errors.append(f"{where}: missing {DOC_FILE[kind]}")
        else:
            fields = frontmatter(doc)
            if fields.get("name") != node["name"] or not fields.get("description"):
                errors.append(f"{where}: {DOC_FILE[kind]} frontmatter needs name '{node['name']}' and a description")
    if kind == "skill":
        if not isinstance(node["vision"], bool):
            errors.append(f"{where}: vision must be true or false")
        for key in ("input", "output"):
            if not isinstance(node[key], dict) or node[key].get("type") != "object":
                errors.append(f"{where}: {key} must be a JSON Schema object")
    return errors


def load() -> Tuple[Dict[str, Dict[str, dict]], List[str]]:
    nodes: Dict[str, Dict[str, dict]] = {kind: {} for kind in KIND_DIRS}
    errors: List[str] = []
    for kind, dirname in KIND_DIRS.items():
        for folder in sorted((REGISTRY / dirname).glob("*/")):
            path = folder / "node.json"
            if not path.is_file():
                errors.append(f"{dirname}/{folder.name}: missing node.json")
                continue
            try:
                node = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{dirname}/{folder.name}: node.json is not valid JSON ({exc})")
                continue
            errors.extend(check_node(kind, folder, node))
            nodes[kind][folder.name] = node
    return nodes, errors


def cross_check(nodes: Dict[str, Dict[str, dict]]) -> List[str]:
    errors = []
    skills, agents = nodes["skill"], nodes["agent"]
    for name, agent in agents.items():
        for step in agent.get("steps", []):
            if step not in skills:
                errors.append(f"agents/{name}: step '{step}' is not a skill in the registry")
            elif set(agent.get("providers", {})) - set(skills[step].get("providers", {})):
                errors.append(f"agents/{name}: step '{step}' does not run on every provider the agent offers")
    for name, plugin in nodes["plugin"].items():
        for skill in plugin.get("skills", []):
            if skill not in skills:
                errors.append(f"plugins/{name}: skill '{skill}' is not in the registry")
        for agent in plugin.get("agents", []):
            if agent not in agents:
                errors.append(f"plugins/{name}: agent '{agent}' is not in the registry")
        offered = set(plugin.get("tools", []))
        for skill in plugin.get("skills", []):
            missing = set(skills.get(skill, {}).get("tools", [])) - offered
            if missing:
                errors.append(f"plugins/{name}: skill '{skill}' uses tools the plugin does not offer: {sorted(missing)}")
    return errors


def build(nodes: Dict[str, Dict[str, dict]]) -> dict:
    entries, edges = [], []
    for kind, dirname in KIND_DIRS.items():
        for name, node in sorted(nodes[kind].items()):
            files = sorted(p.relative_to(REGISTRY.parent).as_posix()
                           for p in (REGISTRY / dirname / name).iterdir() if p.is_file())
            entry = {
                "kind": kind, "name": name, "version": node["version"],
                "description": node["description"], "apps": node["apps"], "files": files,
            }
            for key in ("providers", "requires", "vision", "tools"):
                if key in node:
                    entry[key] = node[key]
            entries.append(entry)
            for order, step in enumerate(node.get("steps", []), start=1):
                edges.append({"from": f"agent:{name}", "to": f"skill:{step}", "type": "calls", "order": order})
            for skill in node.get("skills", []) if kind == "plugin" else []:
                edges.append({"from": f"plugin:{name}", "to": f"skill:{skill}", "type": "contains"})
            for agent in node.get("agents", []) if kind == "plugin" else []:
                edges.append({"from": f"plugin:{name}", "to": f"agent:{agent}", "type": "contains"})
            for tool in node.get("tools", []) if kind == "skill" else []:
                edges.append({"from": f"skill:{name}", "to": f"tool:{tool}", "type": "uses"})
    return {"schemaVersion": 1, "nodes": entries, "edges": edges}


def render(index: dict) -> str:
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if index.json is stale")
    args = parser.parse_args(argv)
    nodes, errors = load()
    errors += cross_check(nodes)
    if errors:
        print("registry: invalid", *errors, sep="\n  ")
        return 1
    text = render(build(nodes))
    count = sum(len(v) for v in nodes.values())
    if args.check:
        if not INDEX.is_file() or INDEX.read_text(encoding="utf-8") != text:
            print("registry: index.json is stale. Run: python3 registry/build_index.py")
            return 1
        print(f"registry: {count} nodes valid, index.json up to date")
        return 0
    INDEX.write_text(text, encoding="utf-8")
    print(f"registry: {count} nodes valid, wrote {INDEX.relative_to(REGISTRY.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
