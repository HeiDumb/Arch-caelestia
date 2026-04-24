# Arch + Caelestia shell

## Layout

- `home/`: files intended to live under `$HOME`
- `home/.config/`: application and desktop configs
- `home/scripts/`: personal helper scripts
- `packages/`: pacman, AUR, flatpak, and enabled user-unit manifests
- `resources/`: exported settings such as dconf
- `docs/`: system info, install notes, exclusions, and export tree
- `setup/bootstrap.sh`: helper restore script

## Included

- shell files: `.bash_profile`, `.bashrc`, `.zprofile`, `.zshrc`
- theme files: `.gtkrc-2.0`, `.icons`, `.themes`
- desktop/session config: `hypr`, `quickshell`, `caelestia`, `uwsm`, `systemd`, `environment.d`
- terminal/launcher/media config: `foot`, `fuzzel`, `rofi`, `mpv`, `cava`, `spicetify`
- utility config: `btop`, `htop`, `nvtop`, `neofetch`, `Thunar`, `qtengine`, `simple-update-notifier`
- editor/app settings: curated `Code - OSS`, `zed`, curated `zen`, curated `discord`, curated `vesktop`, curated `Vencord`
- app/client configs: `BetterDiscord`, `Equicord`, `equibop`, `legcord`, `spotify`, `vlc`, `xfce4`, `Kitware`
- flatpak app config snapshots under `home/.var/app`
- scripts from `/home/hei/scripts`
- package manifests and dconf export

## Caelestia Install

This repo now includes a dedicated Caelestia package manifest at [packages/caelestia-core.txt](packages/caelestia-core.txt). The helper script can install it directly:

```bash
bash setup/bootstrap.sh caelestia
```

That path bootstraps `yay` if needed, then installs:

- `caelestia-shell`
- `caelestia-cli`
- `quickshell-git`
- `wallust`
- `python-materialyoucolor`
- `ttf-rubik-vf`

## Excluded

See [docs/EXCLUDED.md](docs/EXCLUDED.md).

## Quick Start

1. Review [docs/INSTALL.md](docs/INSTALL.md).
2. Initialize git if you want to publish it:

```bash
cd /home/hei/arch-system-repo-2026-04-24
git init
git add .
git commit -m "Initial Arch system export"
```

3. Add a remote and push:

```bash
git remote add origin git@github.com:<your-user>/<your-repo>.git
git branch -M main
git push -u origin main
```

## Safety Notes

- `packages/pacman-explicit.txt` includes kernel, firmware, boot, and driver packages from this machine. Review before installing on different hardware.
- `resources/dconf-settings.ini` can overwrite desktop preferences when loaded.
- `home/.config/systemd/user` and `packages/enabled-user-units-clean.txt` reflect this user session setup and may need trimming on another machine.
- browser and Electron app configs are included in curated form, but cookies, token stores, login databases, and cache trees were intentionally filtered.

## Reference Files

- [docs/system-info.txt](docs/system-info.txt)
- [docs/export-tree.txt](docs/export-tree.txt)
- [packages/pacman-explicit.txt](packages/pacman-explicit.txt)
- [packages/pacman-explicit-raw.txt](packages/pacman-explicit-raw.txt)
- [packages/aur-explicit.txt](packages/aur-explicit.txt)
- [packages/caelestia-core.txt](packages/caelestia-core.txt)
- [packages/flatpak-apps.txt](packages/flatpak-apps.txt)
- [packages/code-oss-extensions.txt](packages/code-oss-extensions.txt)
