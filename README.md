# lshell — Limited Shell (QuickBox.IO fork)

`lshell` is a restricted login shell written in Python. It confines a user to a configurable set of allowed commands, keeps them inside their own directory tree, controls what may run over SSH (scp, sftp, rsync, etc.), and logs their activity.

This is the **QuickBox.IO-maintained fork** of the (now unmaintained) upstream `ghantoos/lshell`. It is packaged as a standard Python wheel, supports Python 3.10–3.13, and carries security hardening specific to the QuickBox Pro seedbox platform.

## Role in QuickBox Pro

On every QuickBox Pro install, `lshell` is the login shell for **shell-level-3 (restricted) non-admin users**. Admin and full-shell users are unaffected. A restricted user who logs in over SSH — or opens a terminal in the dashboard — lands in `lshell` instead of `bash`, and can only run the whitelisted commands their seedbox workflow needs (`rtorrent`, `rclone`, `git`, `rsync`, and so on).

The goal is containment: a restricted user can operate their seedbox but cannot escape into a general-purpose shell, read outside their home tree, or execute arbitrary code on the host.

## Confinement model

Each user's environment is resolved from the configuration file in this order of priority:

1. `[username]` — a section named for the UNIX user
2. `[grp:groupname]` — a section named for the user's UNIX group
3. `[default]` — the fallback applied to everyone

Key controls (see `man lshell` for the full list):

- **`allowed`** — the exact command whitelist (or `'all'` for everything on `PATH`).
- **`forbidden`** — characters and tokens that are rejected outright (`;`, `&`, `|`, backtick, `>`, `<`, `$(`, `${`, `sudo`, `./`, …).
- **`path`** — the directory tree the user is geographically restricted to (e.g. `['/home/%u/']`).
- **`overssh`** — the commands permitted to run non-interactively over SSH.
- **`strict`** — when `1`, any unknown command is treated as forbidden and decrements the user's warning counter.

## Security posture

The fork adds fail-closed exec protection on top of the upstream checks:

- **Enforced `sudo_noexec.so` backstop.** Before each command runs, `lshell` prepends `LD_PRELOAD=<sudo_noexec.so>`, so a "rich" whitelisted binary (an editor, `find`, etc.) cannot `exec()` its way into a subshell.
- **`path_noexec_strict` (QuickBox default).** When set, if the `sudo_noexec.so` library cannot be located, `lshell` **refuses to start** rather than launching a restricted shell with no exec protection. A missing backstop is treated as a hard failure, not a warning.
- **Sanitised environment.** Inherited `LD_PRELOAD`, `LD_LIBRARY_PATH`, and `GCONV_PATH` are stripped and `PATH` is rebuilt from `env_path` / `allowed_cmd_path`, so a user cannot pre-load their own library or point the shell at their own binaries.
- **Traversal-safe path checks.** Directory restrictions resolve real paths and reject wildcard- and dotfile-obfuscated parent-directory traversal (`.*/.*/etc/passwd`, `../../../etc/passwd`, and similar), so a user cannot walk out of their permitted tree.
- **Forbidden-token filtering.** Command separators, redirections, and substitution syntax are blocked so a whitelisted command cannot be chained into an un-whitelisted one.

## Installation and updates

QuickBox installs and updates `lshell` as a **pre-built wheel served by the QuickBox release proxy** — there is no build toolchain on a user's box. The installer and updater:

1. Request the current release artifact from the release proxy.
2. Verify it (non-empty, SHA-256, version-in-filename) **before** installing.
3. `pip install --no-deps` the verified wheel, creating the `lshell` console entry at `/usr/bin/lshell`.

This replaces the old `git clone` + `flit build` flow: no anonymous clone, no on-box build, and no chance of a failed build leaving a dangling shell symlink that locks restricted users out at login.

`lshell` is **not** distributed as a `.deb` or an RPM, and is **not** installed from source on user machines. QuickBox Pro is Debian/Ubuntu only.

## Configuration

The **canonical** QuickBox configuration lives in the v3 repository at `src/config/system/lshell/lshell.conf` and is deployed to `/etc/lshell.conf`. Edit configuration there — do not treat any copy bundled in this repository as the source of truth. The configuration is reloaded dynamically: editing `/etc/lshell.conf` applies to already-connected users on their next command.

## Python support

`lshell` targets **Python 3.10–3.13**. The wheel is `py3-none-any` (interpreter-agnostic) and depends only on the standard library.

## Development and testing

The test suite lives under `test/`:

- **`test_unit.py`** — unit coverage of the security and configuration logic; this is the release gate.
- **`test_functional.py`** — spawns `bin/lshell` via `pexpect` and exercises real confinement behaviour end to end.

Both run in CI (see `.github/workflows/test.yml`) across Python 3.10, 3.11, 3.12, and 3.13 on every push and pull request. To run the unit suite locally:

```bash
python -m unittest discover -s test -p 'test_unit.py' -v
```

Release artifacts (wheel + sdist) are built with `flit` and published by `.github/workflows/release.yml`; the release proxy serves the latest stable wheel to QuickBox servers.

## License and attribution

Licensed under the **GNU General Public License v3** (see `COPYING`).

Originally written by **Ignace Mouzannar (ghantoos)**. This is the QuickBox.IO-maintained fork, kept current for modern Python and hardened for the QuickBox Pro platform.
