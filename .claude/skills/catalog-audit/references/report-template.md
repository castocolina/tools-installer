# Report template

Load this file only while writing one entry's report (step 3 of `SKILL.md`). The
example below is checked against the tool's own validator, so what it shows is
what `write` accepts. Every value in it is illustrative; copy the shape, never a value.

```markdown
# opencode - catalog audit 2026-11-13

## Versions
- pinned: none (the brew method installs whatever the formula serves)
- verified: 2026-10-02
- installed: 1.19.5 (`opencode --version`)
- latest: 1.19.5 (GitHub releases/latest, https://api.github.com/repos/sst/opencode/releases/latest)
- latest: 2.0.0 (npm dist-tag latest, https://registry.npmjs.org/opencode-ai/latest)
- note: major split, GitHub's latest is the 1.x line while the npm latest tag is 2.x

## Changelog
- 2.0.0 renames the permission settings key and changes the upgrade command (release notes, https://github.com/sst/opencode/releases/tag/v2.0.0)
- no install, update, removal, config or MCP note between 1.19.5 and 1.19.5

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the registry installs 1.19.5 while npm serves 2.0.0, https://registry.npmjs.org/opencode-ai/latest |
| update argv | unknown | reason: container check not run (no runtime on this host) |
| removal recipe and paths | ok | `opencode debug paths` lists the data directory ~/.local/share/opencode |
| tuning keys | drift | `installer/agent_settings.py:12` writes a key the 2.0.0 schema marks deprecated |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- switch the opencode install to the npm package; risk: medium; evidence: https://registry.npmjs.org/opencode-ai/latest
```

## Field guide

- Title line: `# <id> - catalog audit <date>`, the id exactly as in the registry, the date the run's date.
- `## Versions`: exactly one `pinned`, `verified` and `installed` line and at least one `latest`
  line. Copy versions verbatim from their source and name the source on the line. When every
  source failed, write `- latest: unknown: <reason>`; an install method or update argv row is
  then never `ok`. A `note:` line explains a split such as a newer major than GitHub's latest.
- `## Changelog`: one `- ` line per note that touches install, update, removal, config or MCP,
  with its URL; when there is none, say so in one line.
- `## Checks`: the five rows in this order, never reordered or merged. The table header and
  separator row are fixed.
  - `ok` or `drift` needs evidence in the source cell: a URL, a command in backticks, or a repo
    citation `path:line`.
  - `unknown` says why in the source cell (`reason: ...`). A row that needs a container and
    got none reads `unknown` with `reason: container check not run (<why>)`.
  - `n/a` means the step cannot apply to this entry; its source starts with `reason: `.
- `## Proposed changes`: `- none`, or one `- <change>; risk: low|medium|high; evidence: <source>`
  line per change.
- Use `~` for the home directory, never an absolute home path, and never quote a credential or a
  config value. The tool appends its completion footer; never write it yourself.
