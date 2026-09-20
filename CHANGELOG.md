# Changelog — SkillKorp M20 Ultimate Linux Driver

Toutes les modifications notables sont documentées dans ce fichier.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.2.0] — 2026-09-20

### Nouvelles fonctionnalités & Améliorations majeures

- **Schéma visuel fidèle et interactif de la souris** : remplacement du dessin SVG générique par le visuel photographique haute résolution fidèle à la souris réelle (corps ergonomique noir mat, molette crantée rétroéclairée, boutons latéraux violets/lilas, logo cyan).
- **Zones cliquables réelles via `Gtk.Overlay`** : 5 zones interactives réelles positionnées directement sur le visuel de la souris (clic gauche, clic droit, molette, bouton avant, bouton arrière) avec mise en surbrillance au survol. Un clic sur une partie de la souris donne le focus et ouvre directement le menu déroulant (`ComboRow.activate()`) associé.
- **Clarification du bouton 6 (DPI Cycle)** : le bouton 6 est explicitement labellisé comme étant situé sous la souris ("6. DPI Cycle (Sous la souris)"), avec une pastille dédiée `[6] DPI (dessous)`.

### Correctifs

- **`m20_gui.py` (`_init_buttons_page`)** : correction de la cause racine de la non-interactivité de l'onglet Boutons en intégrant les `Adw.ComboRow` dans un `Gtk.ListBox` (classe `.boxed-list`), rétablissant la réception des événements de clic et l'ouverture des menus d'action.
- **Nettoyage du code** : suppression de l'attribut inopérant `schematic_card.set_padding = 12`.

---

## [1.1.1] — 2026-09-20

### Correctifs & Améliorations (extension bouton 6)

- **`m20_gui.py` (`_on_restore_buttons_clicked`)** : correction d'un `IndexError` sur `default_keys[5]` lors du clic sur "Restaurer par Défaut". La liste `default_keys` ne contenait que 5 entrées alors que l'interface comporte 6 rangées de boutons depuis la version 1.1.0 (`"dpi_cycle"` ajouté).
- **`m20ctl` (`cmd_button`)** : passage de `range(1, 6)` à `range(1, 7)` dans l'affichage par défaut de `m20ctl button` (sans arguments) pour afficher l'attribution actuelle du bouton 6 (DPI Cycle).
- **`m20_gui.py` (`_sync_ui_from_current_profile`)** : remplacement de la chaîne conditionnelle par la liste `default_actions = ["left_click", "right_click", "middle_click", "forward", "backward", "dpi_cycle"]`, assurant que le bouton 6 retombe bien sur `"dpi_cycle"` si sa clé est absente d'un profil importé.

---

## [1.1.0] — 2026-09-20

### Bugs critiques corrigés

- **`m20_driver.py` — `set_power_settings()`** : correction de la variable non définie `move_wake` → `move_to_wake` (provoquait une `NameError` à chaque appel).
- **`m20_driver.py` — `apply_all()` et `profile_manager.py` — `apply_profile_to_driver()`** : ajout de l'appel manquant à `set_rgb_lighting()`. Les paramètres RGB (mode, luminosité, couleur) n'étaient jamais réappliqués lors d'un changement de profil ou d'un `m20ctl apply`.
- **`m20_driver.py` — `query_status()`** : protection contre `IndexError` si `active_stage` est supérieur au nombre d'étapes DPI (clamp défensif `max(1, min(active_stage, len(stages)))`).
- **`m20_driver.py` — `set_dpi_and_sensor()`** : clamp de `cur_active` contre `len(current_stages)` si les étapes sont réduites après chargement du profil.
- **`packaging/arch/PKGBUILD`** : corrigé lors du commit précédent — la fonction `package()` n'installait ni `profile_manager.py` ni `m20_tray.py` ni les `assets/`, et ne créait pas le lien `m20-tray`. Toute installation via `makepkg -si` plantait avec `ModuleNotFoundError`.

### Nouvelles fonctionnalités

- **Bouton 6 (DPI Cycle) accessible** : la CLI (`m20ctl button --btn 1..6`) et la GUI (6e `ComboRow` "DPI Cycle - Bas du pouce") exposent désormais le bouton 6.
- **Détection fiable du tray** : `m20_tray.py` écrit son PID dans `~/.config/skillkorp-m20/tray.pid` au démarrage et le supprime à l'arrêt. `get_tray_pids()` dans `m20ctl` lit ce fichier en priorité (avec vérification que le processus est vivant), et utilise `pgrep -f "m20_tray\.py|m20-tray"` en fallback.
- **38 tests unitaires pytest** dans `tests/test_driver.py` couvrant : buffers HID et checksums (Report 0x05), encodage DPI (Report 0x04), clamp `active_stage`, mappage slots boutons, validation `import_profile`, constantes du protocole.
- **Workflow CI GitHub Actions** (`.github/workflows/ci.yml`) : lint flake8 (erreurs critiques bloquantes, style non-bloquant) + pytest + smoke tests d'import.

### Bugs moyens corrigés

- **`m20_driver.py` — `_load_or_default_config()` / `_save_config()`** : accès concurrent entre GUI, tray et CLI protégé par `fcntl.flock` (LOCK_SH en lecture, LOCK_EX en écriture avec écriture atomique via fichier `.tmp` + `os.replace`).
- **`packaging/rpm/skillkorp-m20.spec`** : ajout de `Recommends: libayatana-appindicator-gtk3` et `libappindicator-gtk3` pour que le tray fonctionne sur Fedora et autres distributions RPM sans installation manuelle.
- **Duplication `is_autostart_enabled` / `set_autostart`** : les fonctions locales dans `m20_tray.py` sont supprimées. `m20_tray.py` les importe depuis `profile_manager.py` (source de vérité unique).
- **`profile_manager.py` — `import_profile()`** : validation complète avant import : DPI (50-26 000, 1-8 étapes), `active_stage` (dans les bornes), `polling_rate` (125/250/500/1000 Hz uniquement), numéros de boutons (1-6), actions valides (clés de `BUTTON_ACTIONS`).
- **`profile_manager.py` — `DEFAULT_PROFILES`** : les 3 profils prédéfinis incluent désormais les champs `light_mode`, `brightness`, `speed`, `light_color` (nécessaires pour `apply_profile_to_driver`).

### Bugs mineurs corrigés

- **`udev/99-skillkorp-m20.rules`** : `MODE="0666"` remplacé par `MODE="0660"` — `TAG+="uaccess"` suffit pour la session logind, `0666` était redondant et trop permissif.
- **Menu tray** : les sous-menus (DPI, polling rate, profils) ne sont reconstruits que si les données ont changé depuis le dernier cycle — évite une reconstruction inutile toutes les 2 secondes.
- **Exceptions silencieuses** : `_save_config()` dans `m20_driver.py` et `_load_state()` dans `profile_manager.py` loguent désormais les erreurs sur `sys.stderr` au lieu de les avaler silencieusement.

---

## [1.0.0] — 2026-09-10

### Version initiale

- Pilote HID natif Linux pour SkillKorp M20 Ultimate (1d57:fa60 sans fil, 1d57:fa61 USB-C)
- CLI `m20ctl` : DPI, polling rate, boutons, profils, veille, tray, autostart
- GUI GTK4/Adw `m20-gui` : toutes les fonctionnalités avec schéma SVG de la souris
- Tray AppIndicator `m20-tray` : batterie temps réel, changement DPI/profil/polling en un clic
- Gestionnaire de profils multi-profils avec auto-switch par application
- Paquets de distribution : `.deb`, `.rpm`, `PKGBUILD` Arch, tarball auto-installe
- Règles udev sans `sudo` au runtime, fichier `.desktop` et icône intégrés
