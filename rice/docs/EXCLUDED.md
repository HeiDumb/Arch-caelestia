# Excluded From Export

These were intentionally not copied into the repo export:

- browser and app session storage
- cookies, local databases, and auth state
- Discord and Discord-client runtime data
- Electron app caches and token stores
- browser login/key stores such as `logins.json`, `key4.db`, `cert9.db`, cookies, and history databases
- Spotify runtime state outside curated Spicetify config
- VS Code global storage and workspace databases
- large wallpaper/runtime asset folders:
  - `/home/hei/swww` (`1.9G`)
  - `/home/hei/linux-wallpaperengine` (`4.0G`)
- caches and compiled Python bytecode where practical
- obvious secret-bearing files such as GPG, PKI, and pulse cookies

The goal was a repo you can safely publish and realistically clone, not a byte-for-byte home-directory image.

Included instead of full dumps:

- curated `discord` config files such as `settings.json` and `Preferences`
- curated `zen` profile config such as `prefs.js`, `user.js`, `chrome/`, and Zen-specific JSON files
- curated `Code - OSS` user settings plus extension list
- curated Flatpak app config files under `home/.var/app`
