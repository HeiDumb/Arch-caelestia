This repo is the version of my Arch setup that is actually worth keeping.

This setup includes the desktop and shell side, the Caelestia side, package manifests, helper scripts, service definitions, and curated app configs.

The repo is organized like this:

- `home/` is the part that belongs in `$HOME`
- `home/.config/` contains desktop and app configs
- `home/scripts/` contains helper scripts
- `packages/` contains pacman, AUR, Flatpak, and extension manifests
- `resources/` contains exported settings like `dconf`
- `docs/` contains extra restore notes, exclusions, system info, and the exported tree
- `setup/bootstrap.sh` is the main helper script for rebuilding the setup

The core components of the rice is here already: Hyprland, Quickshell, Caelestia, shell files, themes, user services, launcher and terminal config, media tools, and curated configs for things like Discord clients, Zen, Code - OSS, Spotify, VLC, and more.

## Initialization And Requirements

Before starting, you should have:

-  `git`, `rsync`, `base-devel`, and `flatpak` pkgs

Install the base tools first:

```bash
sudo pacman -S --needed git rsync base-devel flatpak
```

Clone the repo:

```bash
git clone git@github.com:<your-user>/rice.git
cd rice
```

If you want to review what will be installed before doing anything big, check these first:

```bash
sed -n '1,200p' packages/pacman-explicit.txt
sed -n '1,200p' packages/aur-explicit.txt
sed -n '1,200p' packages/caelestia-core.txt
```

The Caelestia stack used by this setup is listed in [packages/caelestia-core.txt](packages/caelestia-core.txt). The bootstrap script can install it directly when needed.

## Starting The Setup

If you want the fast path, run everything:

```bash
bash setup/bootstrap.sh all
```

If you want to do it in pieces instead, the usual order is:

```bash
bash setup/bootstrap.sh packages
bash setup/bootstrap.sh caelestia
bash setup/bootstrap.sh flatpaks
bash setup/bootstrap.sh sync
bash setup/bootstrap.sh dconf
bash setup/bootstrap.sh services
```

What those steps do:

- `packages` installs the official repo package list
- `caelestia` installs the Caelestia-related stack this setup expects
- `flatpaks` installs the exported Flatpak apps
- `sync` copies the curated `home/` files into place
- `dconf` restores exported desktop preferences
- `services` reloads and enables the exported user services

## Finalization

Once the restore is done, finish it off with:

```bash
systemctl --user daemon-reload
xargs -a packages/enabled-user-units-clean.txt -r systemctl --user enable
xargs -a packages/enabled-user-units-clean.txt -r systemctl --user start
```

After that, log out and back in, or just reboot if you want the cleanest first boot into the restored setup.

If you changed anything locally and want to keep this repo updated too:

```bash
cd /home/hei/rice
git add .
git commit -m "Update rice"
```

## Helpful Tips

- Use a dry run before syncing if you are restoring onto a system that already has your own files: `rsync -avn --delete home/ ~/`
- `packages/pacman-explicit.txt` is the clean official-repo list. The original mixed snapshot is still kept as [packages/pacman-explicit-raw.txt](packages/pacman-explicit-raw.txt).
- Browser and Electron app configs were copied in a curated way. Cookies, token stores, login databases, and caches were intentionally left out.
- `resources/dconf-settings.ini` can overwrite desktop preferences, so do not load it blindly if the target machine already has custom GNOME or GTK settings you want to keep.
- `home/.config/systemd/user` and [packages/enabled-user-units-clean.txt](packages/enabled-user-units-clean.txt) reflect this specific session setup, so some units may need trimming on different hardware.
- If you want more detail, the longer walkthrough is in [docs/INSTALL.md](docs/INSTALL.md), the exclusions are in [docs/EXCLUDED.md](docs/EXCLUDED.md), and the machine snapshot is in [docs/system-info.txt](docs/system-info.txt).
