"""Shared source-exploration guidance for supported coding agents."""

AGENT_TOOLING_MARKDOWN = """\
# Agent tooling guidance

Prefer focused tools when they fit the task: use rg instead of recursive grep,
fd instead of most find, bat for code viewing, eza for directory inspection,
and delta or difftastic for diffs. Use uv rather than bare pip/system Python workflows,
and pnpm rather than bare npm global installs. These choices reduce unnecessary output
and context use; use legacy tools when their unique behavior is needed.

## CodeGraph protocol

At the start of a session or in an unfamiliar repository, check whether
CodeGraph is initialized and current. Run codegraph init once for an
uninitialized repository. Prefer codegraph_explore for architecture and
cross-reference questions before broad file reads.

After initialization, rely on the MCP watcher and connection-time
reconciliation during normal work. Use codegraph status to check health,
codegraph sync only when the watcher is disabled or a script needs a
known-fresh graph, and codegraph index for a deliberate full rebuild after
source, dependency, or structural changes. Treat results as navigational
evidence and read authoritative source files before editing.
"""
