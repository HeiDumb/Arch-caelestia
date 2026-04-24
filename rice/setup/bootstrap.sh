#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-all}"

run() {
  echo "+ $*"
  "$@"
}

ensure_yay() {
  if command -v yay >/dev/null 2>&1; then
    return
  fi

  echo "yay not found. Bootstrapping yay from AUR."
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN

  run git clone https://aur.archlinux.org/yay.git "$tmpdir/yay"
  (
    cd "$tmpdir/yay"
    run makepkg -si --noconfirm
  )
}

install_native_packages() {
  echo "Installing official pacman packages from packages/pacman-explicit.txt"
  run xargs -a "$repo_root/packages/pacman-explicit.txt" sudo pacman -S --needed
}

install_aur_packages() {
  ensure_yay
  echo "Installing AUR packages from packages/aur-explicit.txt"
  run xargs -a "$repo_root/packages/aur-explicit.txt" yay -S --needed
}

install_caelestia() {
  ensure_yay
  echo "Installing Caelestia stack from packages/caelestia-core.txt"
  run xargs -a "$repo_root/packages/caelestia-core.txt" yay -S --needed
}

install_packages() {
  install_native_packages
  install_aur_packages
}

install_flatpaks() {
  if ! command -v flatpak >/dev/null 2>&1; then
    echo "Skipping flatpaks because flatpak is not installed."
    return
  fi

  while IFS= read -r app; do
    [ -n "$app" ] || continue
    run flatpak install -y flathub "$app"
  done < "$repo_root/packages/flatpak-apps.txt"
}

sync_home() {
  echo "Syncing repo home/ into \$HOME"
  run rsync -av --delete "$repo_root/home/" "$HOME/"
}

load_dconf() {
  if command -v dconf >/dev/null 2>&1; then
    echo "Loading dconf settings"
    run bash -lc "dconf load / < '$repo_root/resources/dconf-settings.ini'"
  else
    echo "Skipping dconf because dconf is not installed."
  fi
}

enable_services() {
  echo "Reloading and enabling user services"
  run systemctl --user daemon-reload
  run xargs -a "$repo_root/packages/enabled-user-units-clean.txt" -r systemctl --user enable
}

case "$action" in
  packages)
    install_packages
    ;;
  caelestia)
    install_caelestia
    ;;
  flatpaks)
    install_flatpaks
    ;;
  sync)
    sync_home
    ;;
  dconf)
    load_dconf
    ;;
  services)
    enable_services
    ;;
  all)
    install_packages
    install_caelestia
    install_flatpaks
    sync_home
    load_dconf
    enable_services
    ;;
  *)
    echo "Usage: $0 {packages|caelestia|flatpaks|sync|dconf|services|all}" >&2
    exit 1
    ;;
esac
