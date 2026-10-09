# Alacritty on Bazzite and in the tools-installer catalog

Research recorded 2026-10-09. No Alacritty install was performed. This note does not add a registry entry or change installer code.

## Decision

Catalog Alacritty the way `kitty` is cataloged: native packages on mutable Fedora, Debian, and Arch. Do not compile it from this repo. Do not add a `github_release` method. There is no Homebrew formula, and the Homebrew cask is macOS-only and disabled.

On this Bazzite host, the install that stays off ostree is a Fedora Distrobox plus `distrobox-export`. That path is outside the installer's method kinds, so a catalog row still has no applicable method on immutable Fedora. That is the same accepted gap already documented for `kitty`.

A userspace binary is usable without a reboot. A reboot is required only when the package, or the `-devel` libraries needed to compile it, is layered with `rpm-ostree`.

The version checker goes to GitHub only for an installer-owned tool that has an applicable `github_release` method. A distro-package install is owned by `dnf`, `apt`, or `pacman` and is reported as managed by that manager. It is not compared with the GitHub tag.

## Host this was checked against

Read-only check on 2026-10-09:

- Image: `ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable`
- Booted deployment: `44.20260921` (2026-09-21T05:56:49Z), digest `sha256:dcda4d1a0437b2dd2d4f7435e86997483d616031668402ff40a385571a12d894`
- Desktop: KDE, Wayland
- Already layered, and left untouched: `amdgpu_top`, `coolercontrol`, `liquidctl`, `podman-compose`
- Present: `/usr/bin/distrobox` 1.8.2.5, `/home/linuxbrew/.linuxbrew/bin/brew`, `/usr/bin/flatpak`
- `distrobox list` showed no containers
- `flatpak search alacritty` returned no matches
- `brew search alacritty` returned nothing
- `alacritty` was not on `PATH`

`rpm-ostree` is already in use for those four packages. Adding Alacritty there would add a fifth layer and require a reboot. That is the path this research rejects.

## What Bazzite says to use instead of a layer

[Installing and Managing Applications](https://docs.bazzite.gg/Installing_and_Managing_Software/) ranks formats, most recommended first:

1. Bazzite Portal / `ujust` for a small maintained set. No Alacritty recipe.
2. Bazaar / Flatpak for graphical apps.
3. Homebrew for command-line tools.
4. Distrobox when the package is not in Flatpak or Homebrew. `distrobox-export --app <package>` publishes a GUI into the host menu. `distrobox-export --bin` publishes a CLI.
5. AppImage from a trusted upstream, integrated with Gear Lever.
6. `rpm-ostree` last. Layered packages can block upgrades and rebases until removed. `rpm_ostree` is also hardcoded off in this repo (`installer/resolve.py`, kind `rpm_ostree` always returns false).

Bazzite's own account states the same order: Flatpak, brew, and distrobox before `rpm-ostree` ([docs](https://docs.bazzite.gg/Installing_and_Managing_Software/rpm-ostree/), [Homebrew](https://docs.bazzite.gg/Installing_and_Managing_Software/Homebrew/), [Distrobox](https://docs.bazzite.gg/Installing_and_Managing_Software/Distrobox/)).

## Practical install on this machine, outside the catalog

Fedora 44 official repos ship `alacritty` 0.17.0, the same version as the current GitHub tag. A Fedora 44 container matches the host's major version and this machine's AMD GPU, so Distrobox's `--nvidia` flag does not apply.

```bash
distrobox create --name fedora-44 \
  --image registry.fedoraproject.org/fedora:44 \
  --yes
distrobox enter fedora-44 -- sudo dnf install -y alacritty
distrobox enter fedora-44 -- distrobox-export --app alacritty
```

The exported launcher lands at `~/.local/share/applications/alacritty-fedora-44.desktop`. KDE picks it up under System Settings, Apps, Default Applications, Terminal.

The exported app starts a shell inside the container. Point Alacritty at the host shell so `ujust`, `brew`, and `flatpak` stay available. Distrobox 1.8.2.5 documents `distrobox-host-exec` for that. Config file, shared through `$HOME`:

```toml
[terminal.shell]
program = "/usr/bin/distrobox-host-exec"
args = ["bash", "-l"]
```

`~/.config/alacritty/alacritty.toml` is the 0.17 TOML location. Confirm the `terminal.shell` key against the man page inside the container after install.

If a host program reports that the terminal type `alacritty` is unknown, install the terminfo into the home directory. That does not touch ostree:

```bash
distrobox enter fedora-44 -- infocmp -x alacritty > /tmp/alacritty.terminfo
tic -x -o ~/.terminfo /tmp/alacritty.terminfo
```

Afterward, `rpm-ostree status` should still list only the four layered packages above. Rootless container storage lives under the user, not in the deployment.

This Distrobox flow is the host recipe. It is not a registry method. The installer has no `distrobox` kind.

## GitHub releases

Latest release: [v0.17.0](https://github.com/alacritty/alacritty/releases/tag/v0.17.0), published 2026-04-06. Tag commit `94e7c88`. Assets from `https://api.github.com/repos/alacritty/alacritty/releases/latest`:

| Asset | What it is |
| --- | --- |
| `Alacritty-v0.17.0.dmg` | macOS app |
| `Alacritty-v0.17.0-installer.msi`, `Alacritty-v0.17.0-portable.exe` | Windows |
| `Alacritty.desktop`, `Alacritty.svg` | Menu entry and icon |
| `alacritty.info` | Terminfo source |
| `alacritty.1.gz`, `alacritty.5.gz`, `alacritty-bindings.5.gz`, `alacritty-msg.1.gz`, `alacritty-escapes.7.gz` | Man pages |
| `alacritty.bash`, `alacritty.fish`, `_alacritty` | Shell completions |
| Source zip and tar.gz | Source, not a build |

There is no Linux binary, AppImage, `.deb`, or `.rpm` in that release. Older tags follow the same split. Upstream expects Linux to come from a distribution package or from a local build.

Release notes worth knowing for a cataloged 0.17: TOML 1.1 syntax, `window.resize_increments` on Wayland, mouse-wheel bindings, a new `alacritty-escapes(7)` man page, and the broken `flash` terminfo capability removed.

Fedora's package of the same version already includes the binary, desktop file, terminfo, man pages, and completions ([Fedora package page](https://packages.fedoraproject.org/pkgs/rust-alacritty/alacritty)). Downloading the GitHub release does not produce a newer Linux build than `dnf install alacritty` on Fedora 44.

## INSTALL.md: compile versus the Fedora binary

Source: [INSTALL.md](https://github.com/alacritty/alacritty/blob/master/INSTALL.md) on `master`, read 2026-10-09.

`cargo install alacritty` installs only the binary. Terminfo, the desktop entry, man pages, and shell completions are separate post-build steps, and those steps copy into `/usr` and `/usr/local` with `sudo`.

Fedora build dependencies named by upstream:

```sh
dnf install cmake freetype-devel fontconfig-devel libxcb-devel libxkbcommon-devel g++
```

Plus a Rust toolchain (`rustup`, stable). Wayland-only or X11-only builds are optional cargo feature flags. The default build supports both. The release binary is `target/release/alacritty`.

Post-build that upstream documents, all of it a root write:

- `sudo tic -xe alacritty,alacritty-direct extra/alacritty.info` if `infocmp alacritty` fails
- `sudo cp` of the binary to `/usr/local/bin`, the SVG to `/usr/share/pixmaps`, and `sudo desktop-file-install`
- man pages through `scdoc` and `gzip` into `/usr/local/share/man`
- completions into the shell's user or system completion path

On Bazzite those `-devel` packages and the `/usr` copies are ostree layers. The compiled binary, once it exists in `~/.local/bin`, does not need a reboot. The reboot belongs to `rpm-ostree`, not to the compiler output. Runtime libraries (`fontconfig`, `freetype`, `libxcb`, `libxkbcommon`) are already on the host. The missing pieces are the headers and the toolchain, and those are what force a layer if the build happens on the host.

Building inside the Fedora Distrobox avoids the layer and still needs no reboot. It produces the same 0.17.0 that `dnf install alacritty` already installs in that container, without the desktop file and terminfo unless the post-build steps are repeated into `$HOME` (`~/.local/share/applications`, `~/.terminfo`) instead of `/usr`.

Compiling in this repo is the worse option: more dependencies, a Rust toolchain, manual desktop and terminfo install, and no newer version than Fedora 44's package.

## Homebrew

Checked live:

- `https://formulae.brew.sh/cask/alacritty` — cask `alacritty`, version 0.17.0, macOS >= 11. Disable date 2026-09-01.
- Cask source `Homebrew/homebrew-cask` `Casks/a/alacritty.rb`: URL is the official DMG, `depends_on :macos`, and `disable! date: "2026-09-01", because: :fails_gatekeeper_check`. The disable is the unsigned Apple Silicon build failing Gatekeeper ([alacritty issue 8749](https://github.com/alacritty/alacritty/issues/8749)).
- No Homebrew formula. `formulae.brew.sh` has no Linux bottle. `brew search alacritty` on this machine was empty.
- This repo's `installer/resolve.py` accepts `kind = "cask"` only when `platform.os == "macos"` and Homebrew is present. A Linux cask would not apply here even if one existed. The `kitty` registry comment records that same policy.

Homebrew is not an install path for Alacritty on Bazzite. On macOS the official cask is disabled, so it is not a ready `brew install --cask alacritty` either. Third-party taps that rebuild the app are unsigned and are not a catalog source.

## How this repo decides an update

`installer/version_status.py`:

- `github_repo()` walks `resolve_methods()` and returns the first applicable method whose `kind` is `github_release`, plus its `repo` string. That function selects a latest-version source. It is not an ownership claim.
- `resolve_github_release_status()` probes `tool.cmd --version`, then `resolve_github_tag(repo)`, which fetches `https://api.github.com/repos/<repo>/releases/latest` and reads `tag_name` (`installer/versions.py`). `is_outdated(installed, latest)` is the comparison. Fetches are capped at 20 per refresh.
- `resolve_status()` uses that GitHub path only when `ownership.owner == "installer"` and `github_repo()` found a method. Brew, cask, pnpm, and uv compare against `brew outdated` / `pnpm outdated` / `uv tool list --outdated`. Anything else, including a `dnf`-owned binary, is `source="unknown"` with `latest=None` unless a native-owner message applies.
- `installer/ownership.py` treats `dnf`, `apt`, and `pacman` as native owners. The catalog copy for a dnf-owned tool is "managed by dnf — this installer will not update it".

So a registry row whose only methods are `dnf` / `apt` / `pacman` will not ask GitHub whether Alacritty is outdated. That is current behavior, and it is what `kitty` already does.

`github_release` cannot be added only to feed the checker:

- Rank in `installer/resolve.py`: `github_release` is 20, `dnf` / `apt` / `pacman` are 30. `install_tool` tries methods in that order. A `github_release` row would run first on Fedora and on Bazzite.
- `installer/download.py` builds `https://github.com/<repo>/releases/download/<tag>/<asset>` and extracts or copies that asset into `~/.local`. Alacritty publishes no Linux asset, so the download fails and `dnf` is never reached.
- On Bazzite, native kinds are skipped because `platform.immutable` is true. `github_release` is not skipped. A bad asset template becomes the only attempted method and fails.
- WezTerm is the contrast that works: its release publishes `WezTerm-{ver}-Ubuntu20.04.AppImage` plus a sibling `.sha256`, `raw = true`, `os = ["debian", "fedora"]`, `arch = ["amd64"]`. That is why WezTerm installs on immutable Fedora and why its version check can hit GitHub. Kitty cannot: its Linux assets are `.txz`, and `download.py` extracts with `tar -xzf`. The kitty comment in `installer/registry.toml` (verified 2026-09-06) records that Bazzite gap on purpose.

A future Linux AppImage or tarball with a published checksum would be the moment to copy the WezTerm method. Until that asset exists, the version line follows the distro package.

## Registry shape, if a row is added later

Not part of this save. Recorded so the next edit does not re-decide it.

- `id = "alacritty"`, `cmd = "alacritty"`, `category = "terminal"`, `tier = "user"`, `audience = "human"`. A terminal emulator is a tool the human drives. Tool-onboarding step 3 says the same thing about kitty-shaped tools.
- Methods: `dnf`, `apt`, and `pacman`, each with `package = "alacritty"`. Fedora, Debian, and Arch all ship that package name. Fedora 44's build is 0.17.0, matching the GitHub tag on the day of this research.
- No `kind = "brew"`. No formula exists.
- No `kind = "cask"`. The cask is disabled and macOS-only. This repo would also refuse it on Linux.
- No `kind = "github_release"`. No Linux asset, and the rank would shadow `dnf`.
- No `kind = "rpm_ostree"`. The resolver refuses that kind, and the user constraint is to stay off ostree.
- No compile script. Build dependencies and the `/usr` post-build steps do not fit a userspace method.
- `# Verified` comment must record the date, the release asset list, the disabled cask, the Fedora package version, and the immutable-Fedora gap. That comment is the audit trail tool-onboarding requires.
- Postinstall: none for the binary. Shell integration for zsh already exists for kitty and WezTerm in `installer/terminal_shell.py`. Alacritty's shell setting is a TOML file and is a separate decision. Do not invent a hook in the same change as the package row.
- On Bazzite the row resolves to no method. `docs/catalog-unsupported-tools.md` is the existing place to say so in one paragraph if the row is added. The Distrobox commands stay in this research note, not in the installer.

## Reboot, stated once

| How it gets on the machine | Reboot |
| --- | --- |
| `dnf install alacritty` on mutable Fedora | No |
| Distrobox `dnf install` plus `distrobox-export` | No |
| Binary or terminfo written under `$HOME` or `~/.local` | No |
| `rpm-ostree install alacritty`, or layering `cmake` and the `-devel` packages so the host can compile | Yes, and it changes the deployment |

## Sources

- https://github.com/alacritty/alacritty/releases/tag/v0.17.0
- https://api.github.com/repos/alacritty/alacritty/releases/latest
- https://github.com/alacritty/alacritty/blob/master/INSTALL.md
- https://packages.fedoraproject.org/pkgs/rust-alacritty/alacritty
- https://formulae.brew.sh/cask/alacritty
- https://raw.githubusercontent.com/Homebrew/homebrew-cask/master/Casks/a/alacritty.rb
- https://github.com/alacritty/alacritty/issues/8749
- https://docs.bazzite.gg/Installing_and_Managing_Software/
- https://docs.bazzite.gg/Installing_and_Managing_Software/software-intro/
- https://docs.bazzite.gg/Installing_and_Managing_Software/Homebrew/
- https://docs.bazzite.gg/Installing_and_Managing_Software/Distrobox/
- https://docs.bazzite.gg/Installing_and_Managing_Software/rpm-ostree/
- Repo: `installer/registry.toml` kitty and wezterm entries, `installer/resolve.py`, `installer/download.py`, `installer/version_status.py`, `installer/versions.py` `resolve_github_tag`, `installer/ownership.py`
