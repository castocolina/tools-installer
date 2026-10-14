"""Self-check: idempotent, user entries win, router-env untouched, MCP conversion. Run: python3 -I test_pi_sync.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pi_sync as s

oc = {
    "opencode/new-model": {"id": "new-model", "name": "New", "api": {"npm": "@ai-sdk/openai-compatible"},
                           "capabilities": {"toolcall": True, "output": {"text": True}}, "limit": {"context": 1000, "output": 100}},
    "opencode/known": {"id": "known", "api": {"npm": "@ai-sdk/openai"}, "capabilities": {"toolcall": True, "output": {"text": True}}},
    "router-env/my-coding": {"id": "my-coding", "api": {"npm": "@ai-sdk/openai-compatible"}},
    "xai/grok-build-0.1": {"id": "grok-build-0.1", "api": {"npm": "@ai-sdk/xai"}, "capabilities": {"toolcall": True, "output": {"text": True}}},
}
catalog = {"opencode": {"known"}, "xai": set()}
user = {"providers": {"router-env": {"apiKey": "LITERAL", "models": [{"id": "my-coding"}]},
                      "opencode": {"apiKey": "$MY_OWN", "models": [{"id": "new-model", "name": "mine"}]}}}

cand, notes = s.plan_models(oc, {}, {"opencode"}, catalog, user)
assert cand["providers"]["router-env"] == user["providers"]["router-env"], "router-env must be untouched"
assert cand["providers"]["opencode"]["apiKey"] == "$MY_OWN", "user credential wins"
assert cand["providers"]["opencode"]["models"] == [{"id": "new-model", "name": "mine"}], "user model wins"
assert "xai" not in cand["providers"], "pi-removed model not re-added"
assert cand["providers"]["opencode-go"] if "opencode-go" in cand["providers"] else True

fresh, _ = s.plan_models(oc, {}, {"opencode"}, catalog, {"providers": {}})
assert fresh["providers"]["opencode"]["apiKey"].startswith("!jq ")
assert [m["id"] for m in fresh["providers"]["opencode"]["models"]] == ["new-model"]
again, _ = s.plan_models(oc, {}, {"opencode"}, catalog, fresh)
assert again == fresh, "second run must be a no-op"

cfg = {"mcp": {"a": {"type": "local", "command": ["x", "y"], "environment": {"K": "{env:TOK}"}},
               "b": {"type": "remote", "url": "https://h/mcp"}, "c": {"type": "local", "command": ["z"], "enabled": False}}}
mcp, _ = s.plan_mcp(cfg, {"mcpServers": {"b": {"url": "https://mine"}}})
assert mcp["mcpServers"]["a"] == {"command": "x", "args": ["y"], "env": {"K": "${TOK}"}}
assert mcp["mcpServers"]["b"] == {"url": "https://mine"} and "c" not in mcp["mcpServers"]
assert s.redact('"apiKey": "sk-123"') == '"apiKey": "<redacted>"' and s.redact('"apiKey": "$X"') == '"apiKey": "$X"'
print("ok")
