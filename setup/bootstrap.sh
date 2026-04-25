#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-guided}"
home_filter="$repo_root/home/.rsync-filter"
selected_list=""
temp_files=()

cleanup() {
  if ((${#temp_files[@]})); then
    rm -f "${temp_files[@]}"
  fi
}
trap cleanup EXIT

run() {
  echo "+ $*"
  "$@"
}

usage() {
  cat >&2 <<'USAGE'
Usage: setup/bootstrap.sh {guided|packages|caelestia|flatpaks|sync|sync-dry-run|sync-clean|dconf|services|all}

  guided       Ask what to install, sync, restore, enable, and start. This is the default.
  sync         Copy repo home/ files into $HOME without deleting existing files.
  sync-clean   Mirror repo home/ into $HOME and move deleted/replaced files to ~/.rice-sync-backups/.
  all          Run the whole restore without prompts.
USAGE
}

make_temp_file() {
  local file
  file="$(mktemp)"
  temp_files+=("$file")
  printf '%s\n' "$file"
}

clean_list_to_file() {
  local source_file="$1"
  local output_file="$2"

  sed '/^[[:space:]]*$/d; /^[[:space:]]*#/d' "$source_file" > "$output_file"
}

list_count() {
  local list_file="$1"

  if [[ ! -s "$list_file" ]]; then
    printf '0\n'
    return
  fi

  wc -l < "$list_file" | tr -d '[:space:]'
}

prompt_yes_no() {
  local question="$1"
  local default="${2:-y}"
  local prompt answer

  case "$default" in
    y|Y|yes|YES)
      default="y"
      prompt="[Y/n]"
      ;;
    n|N|no|NO)
      default="n"
      prompt="[y/N]"
      ;;
    *)
      echo "Invalid prompt default: $default" >&2
      return 2
      ;;
  esac

  while true; do
    read -r -p "$question $prompt " answer
    answer="${answer:-$default}"
    answer="${answer,,}"

    case "$answer" in
      y|yes)
        return 0
        ;;
      n|no)
        return 1
        ;;
      *)
        echo "Please answer yes or no."
        ;;
    esac
  done
}

require_interactive() {
  if [[ ! -t 0 || ! -t 1 ]]; then
    echo "Guided mode needs an interactive terminal. Use 'all' or a specific step for non-interactive runs." >&2
    exit 1
  fi
}

parse_selection() {
  local spec="$1"
  local count="$2"
  local source_file="$3"
  local output_file="$4"
  local nums_file token start end n

  nums_file="$(make_temp_file)"
  : > "$nums_file"

  IFS=',' read -ra tokens <<< "$spec"
  for token in "${tokens[@]}"; do
    token="${token//[[:space:]]/}"
    [[ -n "$token" ]] || continue

    if [[ "$token" =~ ^[0-9]+$ ]]; then
      start="$token"
      end="$token"
    elif [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
      start="${BASH_REMATCH[1]}"
      end="${BASH_REMATCH[2]}"
    else
      return 1
    fi

    if ((start < 1 || end < 1 || start > count || end > count || start > end)); then
      return 1
    fi

    for ((n = start; n <= end; n++)); do
      printf '%s\n' "$n" >> "$nums_file"
    done
  done

  if [[ ! -s "$nums_file" ]]; then
    : > "$output_file"
    return 0
  fi

  sort -n -u "$nums_file" | awk 'NR == FNR { wanted[$1] = 1; next } FNR in wanted' - "$source_file" > "$output_file"
}

choose_items_from_file() {
  local source_file="$1"
  local label="$2"
  local clean_file output_file edited_file choice count editor

  clean_file="$(make_temp_file)"
  output_file="$(make_temp_file)"
  clean_list_to_file "$source_file" "$clean_file"
  count="$(list_count "$clean_file")"

  if ((count == 0)); then
    echo "No items found for $label."
    selected_list="$output_file"
    return
  fi

  while true; do
    echo
    echo "$label has $count item(s)."
    echo "Choose: all, none, view, edit, or numbers/ranges like 1-5,9,12."
    read -r -p "$label selection [all]: " choice
    choice="${choice:-all}"
    choice="${choice,,}"

    case "$choice" in
      all|a)
        cp "$clean_file" "$output_file"
        selected_list="$output_file"
        return
        ;;
      none|n|skip)
        : > "$output_file"
        selected_list="$output_file"
        return
        ;;
      view|v|list|l)
        nl -ba "$clean_file"
        ;;
      edit|e)
        edited_file="$(make_temp_file)"
        cp "$clean_file" "$edited_file"
        editor="${VISUAL:-${EDITOR:-vi}}"
        $editor "$edited_file"
        clean_list_to_file "$edited_file" "$output_file"
        selected_list="$output_file"
        return
        ;;
      *)
        if parse_selection "$choice" "$count" "$clean_file" "$output_file"; then
          selected_list="$output_file"
          return
        fi
        echo "That selection did not parse. Try all, none, view, edit, or something like 1-5,9."
        ;;
    esac
  done
}

run_selected_install() {
  local label="$1"
  shift

  local count
  count="$(list_count "$selected_list")"
  if ((count == 0)); then
    echo "Skipping $label; no items selected."
    return
  fi

  echo "Selected $count item(s) for $label."
  "$@" "$selected_list"
}

install_from_list() {
  local list_file="$1"
  shift

  if [[ ! -s "$list_file" ]]; then
    echo "Skipping empty package list: $list_file"
    return
  fi

  run xargs -r -a "$list_file" "$@"
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
  local list_file="${1:-$repo_root/packages/pacman-explicit.txt}"

  echo "Installing official pacman packages from packages/pacman-explicit.txt"
  install_from_list "$list_file" sudo pacman -S --needed
}

install_aur_packages() {
  local list_file="${1:-$repo_root/packages/aur-explicit.txt}"

  ensure_yay
  echo "Installing AUR packages from packages/aur-explicit.txt"
  install_from_list "$list_file" yay -S --needed
}

install_caelestia() {
  local list_file="${1:-$repo_root/packages/caelestia-core.txt}"

  ensure_yay
  echo "Installing Caelestia stack from packages/caelestia-core.txt"
  install_from_list "$list_file" yay -S --needed
}

install_packages() {
  install_native_packages
  install_aur_packages
}

install_flatpaks() {
  local list_file="${1:-$repo_root/packages/flatpak-apps.txt}"

  if ! command -v flatpak >/dev/null 2>&1; then
    echo "Skipping flatpaks because flatpak is not installed."
    return
  fi

  while IFS= read -r app; do
    [ -n "$app" ] || continue
    run flatpak install -y flathub "$app"
  done < "$list_file"
}

sync_home() {
  echo "Syncing repo home/ into \$HOME"
  run rsync -av --filter="merge $home_filter" "$repo_root/home/" "$HOME/"
}

sync_home_dry_run() {
  echo "Previewing repo home/ sync into \$HOME"
  run rsync -avn --filter="merge $home_filter" "$repo_root/home/" "$HOME/"
}

sync_home_clean() {
  local backup_dir="$HOME/.rice-sync-backups/$(date +%Y%m%d-%H%M%S)"

  echo "Mirroring repo home/ into \$HOME"
  echo "Files removed or replaced by rsync will be backed up to $backup_dir"
  run mkdir -p "$backup_dir"
  run rsync -av --delete --backup --backup-dir="$backup_dir" --filter="merge $home_filter" "$repo_root/home/" "$HOME/"
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
  local list_file="${1:-$repo_root/packages/enabled-user-units-clean.txt}"

  echo "Reloading and enabling user services"
  run systemctl --user daemon-reload
  run xargs -a "$list_file" -r systemctl --user enable
}

start_services() {
  local list_file="${1:-$repo_root/packages/enabled-user-units-clean.txt}"

  echo "Starting selected user services"
  run xargs -a "$list_file" -r systemctl --user start
}

guided_install() {
  require_interactive

  echo "Guided rice setup"
  echo "You can accept whole lists, skip them, view them, edit them, or pick numbered ranges."

  if prompt_yes_no "Install official pacman packages?" y; then
    choose_items_from_file "$repo_root/packages/pacman-explicit.txt" "Official pacman packages"
    run_selected_install "official pacman packages" install_native_packages
  fi

  if prompt_yes_no "Install AUR packages?" y; then
    choose_items_from_file "$repo_root/packages/aur-explicit.txt" "AUR packages"
    run_selected_install "AUR packages" install_aur_packages
  fi

  if prompt_yes_no "Install the Caelestia shell stack?" y; then
    choose_items_from_file "$repo_root/packages/caelestia-core.txt" "Caelestia packages"
    run_selected_install "Caelestia packages" install_caelestia
  fi

  if prompt_yes_no "Install Flatpak apps?" y; then
    choose_items_from_file "$repo_root/packages/flatpak-apps.txt" "Flatpak apps"
    run_selected_install "Flatpak apps" install_flatpaks
  fi

  if prompt_yes_no "Preview the home-file sync before copying anything?" y; then
    sync_home_dry_run
  fi

  if prompt_yes_no "Copy the selected dotfiles/configs into \$HOME?" y; then
    if prompt_yes_no "Use mirror mode with --delete? Backups go to ~/.rice-sync-backups/." n; then
      sync_home_clean
    else
      sync_home
    fi
  fi

  if prompt_yes_no "Load dconf desktop settings? This can overwrite existing desktop preferences." n; then
    load_dconf
  fi

  if prompt_yes_no "Enable user services and sockets?" y; then
    choose_items_from_file "$repo_root/packages/enabled-user-units-clean.txt" "User services and sockets"
    run_selected_install "user services and sockets" enable_services

    if prompt_yes_no "Start the selected user services now?" n; then
      run_selected_install "user services and sockets" start_services
    fi
  fi

  echo "Guided setup finished."
}

case "$action" in
  -h|--help|help)
    usage
    ;;
  guided|interactive|wizard)
    guided_install
    ;;
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
  sync-dry-run)
    sync_home_dry_run
    ;;
  sync-clean)
    sync_home_clean
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
    usage
    exit 1
    ;;
esac
