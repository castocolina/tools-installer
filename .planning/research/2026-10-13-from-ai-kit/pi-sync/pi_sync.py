#!/usr/bin/env python3
"""opencode -> pi model/credential/MCP sync. Dry-run by default.

Reads (never prints secret values):
  - `opencode models --verbose`            what opencode can use right now
  - opencode auth.json                     provider NAMES only
  - opencode.jsonc                         custom providers + mcp block
  - pi-ai catalog data dir + models-store  what pi already ships
  - pi models.json / mcp.json              current pi state (merge base)
Writes only with --write (to the pi agent dir) or --out DIR (candidates + diffs).

Merge rules (idempotent, user entries win):
  - never edits or deletes an existing provider key, model entry, or MCP server;
  - adds a credential *reference* (`!jq ...` / `$ENV`) only where pi has none;
  - adds a model only when opencode lists it and pi's catalog does not;
  - router-env is owned by llm-env (setup-local-llm-agents.sh) and is skipped.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path.home()
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
OC_AUTH = XDG_DATA / "opencode/auth.json"

# opencode provider id -> (pi provider id, credential strategy)
#   ("ref", cmd)   models.json apiKey = "!cmd" (reads opencode's key at request time)
#   ("login", txt) user runs pi's own OAuth/API-key login once
#   ("skip", why)  owned elsewhere
BUILTIN = {
    "opencode": ("opencode", ("ref", f"jq -r .opencode.key {OC_AUTH}")),
    "opencode-go": ("opencode-go", ("ref", f"jq -r .opencode.key {OC_AUTH}")),
    "xai": ("xai", ("login", "pi -> /login xai  (Sign in with SuperGrok or X Premium), or export XAI_API_KEY")),
    "openai": ("openai-codex", ("login", "pi -> /login openai-codex  (ChatGPT Plus/Pro OAuth)")),
    "anthropic": ("anthropic", ("login", "pi -> /login anthropic  (Claude Pro/Max OAuth)")),
    "github-copilot": ("github-copilot", ("login", "pi -> /login github-copilot")),
    "openrouter": ("openrouter", ("login", "pi -> /login openrouter, or export OPENROUTER_API_KEY")),
    "router-env": (None, ("skip", "owned by llm-env setup/lib/install-agent-clients.sh")),
}
# Models pi removed on purpose; re-adding them would create dead /model entries.
PI_REMOVED = {
    "xai/grok-build-0.1",  # pi CHANGELOG 0.85.x: "Removed the unavailable ... Grok Build 0.1" (#9093)
    "xai/grok-4.20-0309-reasoning", "xai/grok-4.20-0309-non-reasoning",  # 0.80.9 removal (#6734)
    "xai/grok-4.20-multi-agent-0309",
}
# opencode AI-SDK adapter -> pi api name
NPM_API = {
    "@ai-sdk/openai-compatible": "openai-completions",
    "@ai-sdk/openai": "openai-responses",
    "@ai-sdk/anthropic": "anthropic-messages",
    "@ai-sdk/google": "google-generative-ai",
    "@ai-sdk/xai": "openai-responses",
}


def strip_jsonc(text: str) -> str:
    # shortcut: minimal string-aware JSONC stripper; reuse ai-kit jsonc_edit if this moves into ai-kit
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1]); i += 2; continue
            in_str = c != '"'
        elif c == '"':
            in_str = True; out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            i = text.index("*/", i) + 2; continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def opencode_models(raw: str) -> dict:
    """Parse `opencode models --verbose`: 'provider/id' line followed by a JSON object."""
    parts = re.split(r"^([\w.-]+/[\w.:-]+)\n(?=\{)", raw, flags=re.M)
    return {parts[i]: json.loads(parts[i + 1]) for i in range(1, len(parts), 2)}


def pi_catalog(data_dir: Path, store: dict) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {}
    for f in data_dir.glob("*.json"):
        for by_api in json.loads(f.read_text()).values():
            if isinstance(by_api, dict):  # some data files carry scalar metadata keys
                ids.setdefault(f.stem, set()).update(v["id"] for v in by_api.values() if isinstance(v, dict))
    for prov, entry in store.items():  # pi.dev catalog overlay cached by pi itself
        ids.setdefault(prov, set()).update(m["id"] for m in entry.get("models", []))
    return ids


def is_chat(m: dict) -> bool:
    cap = m.get("capabilities", {})
    return cap.get("toolcall", False) and cap.get("output", {}).get("text", False) \
        and not any(cap.get("output", {}).get(k) for k in ("image", "video", "audio"))


def pi_model(m: dict, api: str) -> dict:
    cap, cost, lim = m.get("capabilities", {}), m.get("cost", {}), m.get("limit", {})
    entry = {"id": m["id"], "name": m.get("name", m["id"]), "api": api,
             "reasoning": bool(cap.get("reasoning")),
             "input": ["text"] + (["image"] if cap.get("input", {}).get("image") else [])}
    if lim.get("context"):
        entry["contextWindow"] = lim["context"]
    if lim.get("output"):
        entry["maxTokens"] = lim["output"]
    if cost:
        c = cost.get("cache", {})
        entry["cost"] = {"input": cost.get("input", 0), "output": cost.get("output", 0),
                         "cacheRead": c.get("read", 0), "cacheWrite": c.get("write", 0)}
    return entry


def plan_models(oc: dict, oc_cfg: dict, oc_auth_names: set, catalog: dict, current: dict):
    cand = json.loads(json.dumps(current or {}))
    provs = cand.setdefault("providers", {})
    notes = []
    by_prov: dict[str, list[dict]] = {}
    for key, m in oc.items():
        by_prov.setdefault(key.split("/", 1)[0], []).append(m)
    for oc_id, models in sorted(by_prov.items()):
        pi_id, (kind, detail) = BUILTIN.get(oc_id, (oc_id, ("custom", "")))
        if kind == "skip":
            notes.append(f"skip  {oc_id}: {detail}"); continue
        if kind == "custom":
            p = (oc_cfg.get("provider") or {}).get(oc_id, {})
            api = NPM_API.get(p.get("npm", ""))
            base = (p.get("options") or {}).get("baseURL")
            if not (api and base):
                notes.append(f"MANUAL {oc_id}: no npm->api mapping or baseURL; add by hand"); continue
            key = (p.get("options") or {}).get("apiKey", "")
            env = re.fullmatch(r"\{env:(\w+)\}", key or "")
            entry = provs.setdefault(pi_id, {})
            entry.setdefault("baseUrl", base); entry.setdefault("api", api)
            if env and "apiKey" not in entry:
                entry["apiKey"] = f"${env.group(1)}"
            elif "apiKey" not in entry:
                notes.append(f"MANUAL {oc_id}: literal key in opencode.jsonc; set apiKey to $ENV or !cmd yourself")
            have = {x["id"] for x in entry.setdefault("models", [])}
            for m in models:
                if m["id"] not in have:
                    entry["models"].append({"id": m["id"]}); notes.append(f"add   {pi_id}/{m['id']}")
            continue
        if kind == "ref":
            if "opencode" in oc_auth_names:  # Zen and Go share one opencode credential
                entry = provs.setdefault(pi_id, {})
                if "apiKey" not in entry:
                    entry["apiKey"] = f"!{detail}"; notes.append(f"cred  {pi_id}: apiKey -> !{detail}")
            else:
                notes.append(f"MANUAL {pi_id}: opencode has no credential for it")
        else:
            notes.append(f"LOGIN {pi_id}: {detail}")
        known = catalog.get(pi_id, set())
        for m in models:
            if m["id"] in known:
                continue
            if f"{pi_id}/{m['id']}" in PI_REMOVED:
                notes.append(f"skip  {pi_id}/{m['id']}: pi removed it from its catalog on purpose"); continue
            api = NPM_API.get(m.get("api", {}).get("npm", ""))
            if not is_chat(m) or not api:
                notes.append(f"skip  {pi_id}/{m['id']}: not a chat+tools model or unknown adapter"); continue
            entry = provs.setdefault(pi_id, {})
            have = {x["id"] for x in entry.setdefault("models", [])}
            if m["id"] not in have:  # user/previous entry wins
                entry["models"].append(pi_model(m, api)); notes.append(f"add   {pi_id}/{m['id']} ({api})")
    return cand, notes


def plan_mcp(oc_cfg: dict, current: dict):
    """pi docs/mcp.md 'Migrate configuration from another client', OpenCode row."""
    cand = json.loads(json.dumps(current or {}))
    servers = cand.setdefault("mcpServers", {})
    notes = []
    for name, s in sorted((oc_cfg.get("mcp") or {}).items()):
        if name in servers:
            notes.append(f"keep  mcp {name}: already in pi mcp.json"); continue
        if s.get("enabled") is False:
            notes.append(f"skip  mcp {name}: disabled in opencode"); continue
        env = {k: re.sub(r"\{env:(\w+)\}", r"${\1}", v) for k, v in (s.get("environment") or {}).items()}
        if s.get("type") == "local":
            cmd = s.get("command") or []
            entry = {"command": cmd[0], "args": cmd[1:]}
        elif s.get("type") == "remote":
            entry = {"url": s["url"]}
            if s.get("headers"):
                entry["headers"] = {k: re.sub(r"\{env:(\w+)\}", r"${\1}", v) for k, v in s["headers"].items()}
        else:
            notes.append(f"MANUAL mcp {name}: unknown type {s.get('type')!r}"); continue
        if env:
            entry["env"] = env
        servers[name] = entry; notes.append(f"add   mcp {name}")
    return cand, notes


def diff(path: Path, old, new) -> str:
    a = json.dumps(old, indent=2).splitlines(True) if old is not None else []
    b = json.dumps(new, indent=2).splitlines(True)
    return "".join(difflib.unified_diff(a, b, str(path), str(path) + " (candidate)"))


def redact(text: str) -> str:
    # shortcut: masks any long sk-/key-looking literal in diffs; llm-env writes the router key literally
    return re.sub(r'("apiKey": ")(?![!$])[^"]+', r'\1<redacted>', text)


def atomic_write(path: Path, data) -> None:
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2); f.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def default_pi_ai_data() -> Path | None:
    """pi-ai catalog next to the installed pi (pnpm: sibling in .pnpm store; npm: nested)."""
    pi = shutil.which("pi")
    if not pi:
        return None
    pkg = Path(pi).resolve().parents[2]  # .../pi-coding-agent/dist/bundle/cli.js
    for p in (pkg.parent / "pi-ai", pkg / "node_modules/@earendil-works/pi-ai"):
        if (p / "dist/providers/data").is_dir():
            return p / "dist/providers/data"
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pi-dir", type=Path, default=Path(os.environ.get("PI_CODING_AGENT_DIR", HOME / ".pi/agent")))
    ap.add_argument("--opencode-config", type=Path, default=XDG_CONFIG / "opencode/opencode.jsonc")
    ap.add_argument("--opencode-models", type=Path, help="saved `opencode models --verbose` output (default: run it)")
    ap.add_argument("--pi-ai-data", type=Path, help="pi-ai dist/providers/data dir (default: from pnpm root -g)")
    ap.add_argument("--out", type=Path, help="write candidates, diffs and report here")
    ap.add_argument("--write", action="store_true", help="apply to --pi-dir (backs up to *.bak)")
    ap.add_argument("--no-mcp", action="store_true")
    a = ap.parse_args(argv)

    raw = a.opencode_models.read_text() if a.opencode_models else subprocess.run(
        ["opencode", "models", "--verbose"], capture_output=True, text=True, timeout=120, check=True).stdout
    oc = opencode_models(raw)
    oc_cfg = json.loads(strip_jsonc(a.opencode_config.read_text())) if a.opencode_config.exists() else {}
    oc_auth = set(load_json(OC_AUTH, {}).keys())  # names only
    data = a.pi_ai_data or default_pi_ai_data()
    if not data:
        print("pi-ai catalog not found next to `pi`; install pi or pass --pi-ai-data", file=sys.stderr); return 2
    catalog = pi_catalog(data, load_json(a.pi_dir / "models-store.json", {}))

    models_path, mcp_path = a.pi_dir / "models.json", a.pi_dir / "mcp.json"
    cur_models, cur_mcp = load_json(models_path, None), load_json(mcp_path, None)
    new_models, notes = plan_models(oc, oc_cfg, oc_auth, catalog, cur_models)
    outputs = [(models_path, cur_models, new_models)]
    if not a.no_mcp:
        new_mcp, mnotes = plan_mcp(oc_cfg, cur_mcp); notes += mnotes
        outputs.append((mcp_path, cur_mcp, new_mcp))

    report = "\n".join(notes) + "\n"
    diffs = {p.name: redact(diff(p, old, new)) for p, old, new in outputs}
    changed = [(p, new) for p, old, new in outputs if old != new]
    print(report, end="")
    print(f"{len(changed)} file(s) would change" + ("" if a.write else " (dry run)"))
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "report.txt").write_text(report)
        for p, _old, new in outputs:
            (a.out / f"candidate-{p.name}").write_text(redact(json.dumps(new, indent=2)) + "\n")
            (a.out / f"{p.stem}.diff").write_text(diffs[p.name] or "(no change)\n")
    if a.write:
        for p, new in changed:
            atomic_write(p, new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
