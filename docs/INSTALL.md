# Install Guide

These are the main commands needed to restore this setup on another Arch-based machine.

## 1. Clone The Repo

```bash
git clone git@github.com:<your-user>/rice.git
cd rice
```

## 2. Install Base Tooling

```bash
sudo pacman -S --needed git rsync base-devel flatpak
```

Install `yay` if needed before restoring AUR packages.

## 3. Review Hardware-Specific Packages

Before bulk installing, inspect:

```bash
sed -n '1,200p' packages/pacman-explicit.txt
sed -n '1,200p' packages/aur-explicit.txt
sed -n '1,200p' packages/caelestia-core.txt
```

Pay special attention to:

- `linux-*`
- `amd-ucode`
- `nvidia-*`
- `vulkan-*`
- bootloader packages

## 4. Install Official Pacman Packages

```bash
xargs -a packages/pacman-explicit.txt sudo pacman -S --needed
```

## 5. Install AUR Packages

```bash
xargs -a packages/aur-explicit.txt yay -S --needed
```

If `yay` is missing:

```bash
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si --noconfirm
cd ..
```

## 6. Install Caelestia Explicitly

The full package restore already includes it, but if you want the shell stack first:

```bash
xargs -a packages/caelestia-core.txt yay -S --needed
```

This installs the core pieces needed for this repo's shell config:

- `caelestia-shell`
- `caelestia-cli`
- `quickshell-git`
- `wallust`
- `python-materialyoucolor`
- `ttf-rubik-vf`

## 7. Install Flatpak Apps

```bash
while IFS= read -r app; do
  flatpak install -y flathub "$app"
done < packages/flatpak-apps.txt
```

## 8. Sync The Home Directory Files

Dry run first:

```bash
bash setup/bootstrap.sh sync-dry-run
```

Apply safely:

```bash
bash setup/bootstrap.sh sync
```

That copies files into place without deleting unrelated local files. If you want the repo to be an exact mirror of the relevant home folders, use:

```bash
bash setup/bootstrap.sh sync-clean
```

`sync-clean` uses `rsync --delete`, but backs up removed or replaced files under `~/.rice-sync-backups/`.

If you do not want a full overwrite, selectively sync directories instead:

```bash
rsync -av home/.config/hypr/ ~/.config/hypr/
rsync -av home/.config/quickshell/ ~/.config/quickshell/
rsync -av home/.config/caelestia/ ~/.config/caelestia/
rsync -av home/scripts/ ~/scripts/
rsync -av home/.config/zen/ ~/.config/zen/
rsync -av home/.config/vesktop/ ~/.config/vesktop/
```

## 9. Restore Dconf Settings

```bash
dconf load / < resources/dconf-settings.ini
```

## 10. Reload And Enable User Services

```bash
systemctl --user daemon-reload
xargs -a packages/enabled-user-units-clean.txt -r systemctl --user enable
```

Start the ones you want immediately:

```bash
xargs -a packages/enabled-user-units-clean.txt -r systemctl --user start
```

## 11. Optional Helper Script

Run the guided helper:

```bash
bash setup/bootstrap.sh
```

It asks before every major phase. For package and service lists, choose `all`, `none`, `view`, `edit`, or numbered selections such as `1-5,9,12`.

Or run the helper in phases:

```bash
bash setup/bootstrap.sh packages
bash setup/bootstrap.sh caelestia
bash setup/bootstrap.sh flatpaks
bash setup/bootstrap.sh sync-dry-run
bash setup/bootstrap.sh sync
bash setup/bootstrap.sh dconf
bash setup/bootstrap.sh services
```

Or run everything without prompts:

```bash
bash setup/bootstrap.sh all
```

## 12. App Config Notes

- `home/.config/discord`, `home/.config/vesktop`, `home/.config/Vencord`, and `home/.config/zen` are included as config snapshots, not full session dumps.
- Flatpak app configs live under `home/.var/app`.
- VS Code extension IDs are exported to `packages/code-oss-extensions.txt`.
- Launch helpers used by Hyprland and user services live under `home/.local/bin`.
