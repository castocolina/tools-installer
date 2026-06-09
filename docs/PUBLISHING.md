# Publishing

`tools-installer` is consumed straight from GitHub: the bootstrap (`install.sh`)
is fetched over HTTPS and run. There is no package to build or upload — "releasing"
means pushing to the public repo so the raw URL resolves.

## One-time: put the repo on GitHub

```sh
gh auth login                       # authenticate once
gh repo create castocolina/tools-installer --public --source=. --remote=origin --push
```

The repo must be **public** so that:

- `https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh`
  is fetchable without authentication, and
- GitHub Actions CI (including the macOS runner) runs for free.

## Verify the one-liner

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
```

## Ongoing: there is no release ceremony

`install.sh` clones `main`, so every `git push` to `main` is "published"
immediately — the raw URL always serves the latest script, and the script always
clones the latest `main`. CI (`.github/workflows/ci.yml`) runs `make validate`
and `make test` on every push and pull request.

To pin to a specific branch, tag, or commit, callers set `TI_REF`:

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | TI_REF=v1.0.0 sh
```
