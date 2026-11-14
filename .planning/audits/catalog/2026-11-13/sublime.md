# sublime - catalog audit 2026-11-13

## Versions
- pinned: 4215 (the app and both Linux tarballs share the version param; the cask is unpinned)
- verified: 2026-11-03
- installed: none (`subl` is not on this host, per the facts block)
- latest: 4215 (Homebrew cask sublime-text, https://formulae.brew.sh/api/cask/sublime-text.json)
- latest: Build 4215 (Sublime Text download page, https://www.sublimetext.com/download)
- note: Sublime publishes no latest URL (registry.toml comment above the sublime app method), so the build comes from the download page and the cask

## Changelog
- pinned equals latest (build 4215); the build's release-notes URL (https://www.sublimetext.com/blog/articles/sublime-text-4215) returned 404, so no note is recorded

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the download page lists the macOS zip and the Linux x64 and arm64 tar.xz builds for build 4215 (https://www.sublimetext.com/download, build_${version} links); the cask sublime-text declares the app and the subl binary (https://formulae.brew.sh/api/cask/sublime-text.json); asset rows in verify-registry.md lines 219-221 |
| update argv | unknown | reason: the registry declares none; the entry comment says the app self-updates after first launch, but no vendor update channel returned a body (https://www.sublimetext.com/updates/4/stable/updates.xml); container check not run (batch rule: no containers) |
| removal recipe and paths | unknown | reason: Sublime's user data directory is not established from the sources read, and the registry declares no config_paths; container check not run (batch rule: no containers) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action |
| postinstall hook | ok | none declared (installer/registry.toml:2554); the entry records no customization in its Verified comment |

## Proposed changes
- after the vendor doc for Sublime's user data directory is found, declare config_paths for it; risk: low; evidence: https://www.sublimetext.com/docs/3/linux.html redirects to a 404 page, so the source is still missing

<!-- catalog-audit:complete -->
