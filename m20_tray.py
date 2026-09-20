#!/usr/bin/env python3
"""
SkillKorp M20 Ultimate - System Tray Indicator & Notifications
Supports:
- Real-time battery status in tray icon & menu
- Low battery alerts & charging notifications via desktop notify
- Instant DPI stage switching from tray menu + OSD notification
- Instant Polling rate switching (125 - 1000 Hz)
- Multi-profile switching from tray menu
- Automatic profile switching based on active application
- Autostart toggle
"""

import os
import sys
import subprocess
import time
from typing import Optional, Dict, List

import gi
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as appindicator
except Exception:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as appindicator

from gi.repository import Gtk, GLib
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    HAS_NOTIFY = True
except Exception:
    HAS_NOTIFY = False

from m20_driver import SkillkorpM20Driver
from profile_manager import ProfileManager, detect_active_window_class

AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, "io.github.skillkorp.m20.tray.desktop")


def is_autostart_enabled() -> bool:
    return os.path.exists(AUTOSTART_FILE)


def set_autostart(enabled: bool):
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    if enabled:
        content = """[Desktop Entry]
Type=Application
Name=SkillKorp M20 Tray
Comment=Indicateur de batterie et raccourcis SkillKorp M20
Exec=m20-tray
Icon=skillkorp-m20
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
        with open(AUTOSTART_FILE, "w") as f:
            f.write(content)
    else:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)


class M20TrayApp:
    def __init__(self):
        self.driver = SkillkorpM20Driver()
        self.pm = ProfileManager()
        if HAS_NOTIFY:
            Notify.init("SkillKorp M20")

        self.last_battery: Optional[int] = None
        self.last_charging: Optional[bool] = None
        self.last_stage: Optional[int] = None
        self.last_connected: Optional[bool] = None
        self.last_active_window: Optional[str] = None
        self.last_profile_id: str = self.pm.get_active_profile_id()
        self.warned_low_20 = False
        self.warned_low_10 = False

        self.indicator = appindicator.Indicator.new(
            "skillkorp-m20-indicator",
            "input-mouse-symbolic",
            appindicator.IndicatorCategory.HARDWARE,
        )
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)

        self._updating_menu = False
        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)

        # Initial check & update
        self._update_status()

        # Check status periodically every 2 seconds
        GLib.timeout_add_seconds(2, self._periodic_check)

    def _get_battery_icon(self, level: int, charging: bool, connected: bool) -> str:
        if not connected:
            return "input-mouse-symbolic"
        if charging:
            return "battery-charging-symbolic"
        if level >= 85:
            return "battery-level-100-symbolic"
        elif level >= 65:
            return "battery-level-80-symbolic"
        elif level >= 45:
            return "battery-level-60-symbolic"
        elif level >= 25:
            return "battery-level-40-symbolic"
        elif level >= 15:
            return "battery-level-20-symbolic"
        else:
            return "battery-level-0-symbolic"

    def _show_notification(self, title: str, message: str, icon: str = "input-mouse-symbolic", urgency: int = 1):
        if not HAS_NOTIFY:
            return
        try:
            notif = Notify.Notification.new(title, message, icon)
            notif.set_urgency(urgency)  # 0: Low, 1: Normal, 2: Critical
            notif.show()
        except Exception as e:
            print(f"[Tray] Erreur notification: {e}", file=sys.stderr)

    def _build_menu(self):
        self._updating_menu = True
        for child in self.menu.get_children():
            self.menu.remove(child)

        # 1. Header item (Device status & battery)
        self.header_item = Gtk.MenuItem(label="SkillKorp M20...")
        self.header_item.set_sensitive(False)
        self.menu.append(self.header_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 2. Profiles Submenu
        self.prof_menu_item = Gtk.MenuItem(label="Profil Actif")
        self.prof_submenu = Gtk.Menu()
        self.prof_menu_item.set_submenu(self.prof_submenu)
        self.menu.append(self.prof_menu_item)

        # 3. DPI Submenu
        self.dpi_menu_item = Gtk.MenuItem(label="Sensibilité DPI")
        self.dpi_submenu = Gtk.Menu()
        self.dpi_menu_item.set_submenu(self.dpi_submenu)
        self.menu.append(self.dpi_menu_item)

        # 4. Polling Rate Submenu
        self.rate_menu_item = Gtk.MenuItem(label="Taux de rapport (Polling)")
        self.rate_submenu = Gtk.Menu()
        self.rate_menu_item.set_submenu(self.rate_submenu)
        self.menu.append(self.rate_menu_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 5. Open GUI
        open_item = Gtk.MenuItem(label="Ouvrir le panneau de contrôle")
        open_item.connect("activate", self._on_open_gui_clicked)
        self.menu.append(open_item)

        # 6. Autostart checkbox
        autostart_item = Gtk.CheckMenuItem(label="Lancer avec la session")
        autostart_item.set_active(is_autostart_enabled())
        autostart_item.connect("toggled", self._on_autostart_toggled)
        self.menu.append(autostart_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # 7. Quit tray
        quit_item = Gtk.MenuItem(label="Quitter l'indicateur")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        self.menu.append(quit_item)

        self.menu.show_all()
        self._updating_menu = False

    def _populate_profile_submenu(self):
        for child in self.prof_submenu.get_children():
            self.prof_submenu.remove(child)

        profiles = self.pm.list_profiles()
        active_id = self.pm.get_active_profile_id()

        group = None
        for p in profiles:
            p_id = p["id"]
            p_name = p.get("name", p_id)
            item = Gtk.RadioMenuItem(label=p_name, group=group)
            if group is None:
                group = item
            if p_id == active_id:
                item.set_active(True)
            item.connect("toggled", self._on_profile_selected, p_id, p_name)
            self.prof_submenu.append(item)

        self.prof_submenu.append(Gtk.SeparatorMenuItem())

        # Auto-switch toggle
        auto_item = Gtk.CheckMenuItem(label="Bascule automatique par jeu/app")
        auto_item.set_active(self.pm.is_auto_switch_enabled())
        auto_item.connect("toggled", lambda it: self.pm.set_auto_switch_enabled(it.get_active()))
        self.prof_submenu.append(auto_item)

        self.prof_submenu.show_all()

    def _populate_dpi_submenu(self, stages, active_stage):
        for child in self.dpi_submenu.get_children():
            self.dpi_submenu.remove(child)

        group = None
        for idx, dpi in enumerate(stages):
            stage_num = idx + 1
            item = Gtk.RadioMenuItem(label=f"Étape {stage_num} : {dpi} DPI", group=group)
            if group is None:
                group = item
            if stage_num == active_stage:
                item.set_active(True)
            item.connect("toggled", self._on_dpi_stage_selected, stage_num, dpi)
            self.dpi_submenu.append(item)
        self.dpi_submenu.show_all()

    def _populate_rate_submenu(self, cur_rate):
        for child in self.rate_submenu.get_children():
            self.rate_submenu.remove(child)

        group = None
        for rate in [125, 250, 500, 1000]:
            item = Gtk.RadioMenuItem(label=f"{rate} Hz", group=group)
            if group is None:
                group = item
            if rate == cur_rate:
                item.set_active(True)
            item.connect("toggled", self._on_rate_selected, rate)
            self.rate_submenu.append(item)
        self.rate_submenu.show_all()

    def _on_profile_selected(self, item, prof_id: str, prof_name: str):
        if self._updating_menu or not item.get_active():
            return
        if self.pm.get_active_profile_id() == prof_id:
            return
        try:
            prof = self.pm.switch_profile(prof_id, driver=self.driver)
            self.last_profile_id = prof_id
            self._show_notification(
                f"Profil activé : {prof_name}",
                f"{prof.get('polling_rate', 1000)} Hz — {prof.get('description', '')}",
                "input-mouse-symbolic",
                urgency=0,
            )
            self._update_status()
        except Exception as e:
            print(f"[Tray] Erreur changement profil: {e}", file=sys.stderr)

    def _on_dpi_stage_selected(self, item, stage_num: int, dpi: int):
        if self._updating_menu or not item.get_active():
            return
        if self.last_stage == stage_num:
            return
        try:
            self.driver.set_dpi_and_sensor(active_stage=stage_num)
            self.last_stage = stage_num
            self._show_notification(
                f"Sensibilité DPI : {dpi} DPI",
                f"Étape {stage_num}/{len(self.driver.config.get('dpi_stages', []))} activée",
                "input-mouse-symbolic",
                urgency=0,
            )
        except Exception as e:
            print(f"[Tray] Erreur changement DPI: {e}", file=sys.stderr)

    def _on_rate_selected(self, item, rate: int):
        if self._updating_menu or not item.get_active():
            return
        if self.driver.config.get("polling_rate") == rate:
            return
        try:
            self.driver.set_polling_rate(rate)
            self._show_notification(
                f"Taux de rapport USB : {rate} Hz",
                "Paramètre mis à jour sur la souris",
                "input-mouse-symbolic",
                urgency=0,
            )
        except Exception as e:
            print(f"[Tray] Erreur changement polling: {e}", file=sys.stderr)

    def _on_open_gui_clicked(self, _):
        try:
            subprocess.Popen(["m20-gui"])
        except Exception:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m20_gui.py")
            subprocess.Popen([sys.executable, script_path])

    def _on_autostart_toggled(self, item):
        set_autostart(item.get_active())

    def _update_status(self):
        connected = self.driver.is_connected()
        status = self.driver.query_status() if connected else None

        if not connected:
            self.header_item.set_label("○ Souris déconnectée")
            self.indicator.set_icon_full("input-mouse-symbolic", "Souris déconnectée")
            if self.last_connected is True:
                self._show_notification("SkillKorp M20 déconnectée", "Le dongle ou la souris n'est plus détecté.", urgency=1)
            self.last_connected = False
            return

        self.last_connected = True
        battery = status["battery"]
        charging = status["charging"]
        active_stage = status["active_stage"]
        active_dpi = status["active_dpi"]
        stages = status["stages"]
        polling = status["polling_rate_hz"]

        # 1. Update icon & title
        icon_name = self._get_battery_icon(battery, charging, True)
        active_prof = self.pm.get_active_profile_id()
        desc = f"SkillKorp M20 : {battery}% ({active_dpi} DPI) - {active_prof}"
        self.indicator.set_icon_full(icon_name, desc)

        if charging:
            label_text = f"⚡ En charge : {battery}%"
        else:
            label_text = f"🔋 Batterie : {battery}%"
        self.header_item.set_label(f"● SkillKorp M20 — {label_text}")

        # 2. Update submenus
        self._updating_menu = True
        self._populate_profile_submenu()
        self._populate_dpi_submenu(stages, active_stage)
        self._populate_rate_submenu(polling)
        self._updating_menu = False

        # 3. Detect hardware DPI button press
        if self.last_stage is not None and active_stage != self.last_stage:
            self._show_notification(
                f"DPI : {active_dpi}",
                f"Étape {active_stage}/{len(stages)}",
                "input-mouse-symbolic",
                urgency=0,
            )
        self.last_stage = active_stage

        # 4. Battery alerts
        if not charging:
            if battery <= 10 and not self.warned_low_10:
                self._show_notification(
                    "⚠️ Batterie critique : 10%",
                    "Veuillez connecter votre souris en USB-C immédiatement.",
                    "battery-level-0-symbolic",
                    urgency=2,
                )
                self.warned_low_10 = True
            elif battery <= 20 and not self.warned_low_20:
                self._show_notification(
                    "Batterie faible : 20%",
                    "Pensez à brancher votre souris prochainement.",
                    "battery-level-20-symbolic",
                    urgency=1,
                )
                self.warned_low_20 = True
        else:
            if battery > 25:
                self.warned_low_20 = False
                self.warned_low_10 = False

            if self.last_charging is False:
                self._show_notification("⚡ Souris en charge", f"Niveau actuel : {battery}%", "battery-charging-symbolic", urgency=0)

        self.last_battery = battery
        self.last_charging = charging

    def _check_auto_profile_switch(self):
        """Checks if active window requires switching profile."""
        if not self.pm.is_auto_switch_enabled():
            return

        win_class = detect_active_window_class()
        if not win_class or win_class == self.last_active_window:
            return

        self.last_active_window = win_class
        current_prof_id = self.pm.get_active_profile_id()

        # Check all profiles to find match
        for p in self.pm.list_profiles():
            apps = p.get("auto_switch_apps", [])
            for app_pattern in apps:
                if app_pattern.lower() in win_class:
                    if p["id"] != current_prof_id:
                        prof = self.pm.switch_profile(p["id"], driver=self.driver)
                        self._show_notification(
                            f"🎮 Profil automatique : {prof.get('name')}",
                            f"Activé pour '{win_class}'",
                            "input-gaming-symbolic",
                            urgency=0,
                        )
                        self._update_status()
                    return

    def _periodic_check(self) -> bool:
        try:
            self._update_status()
            self._check_auto_profile_switch()
        except Exception as e:
            print(f"[Tray] Erreur périodique: {e}", file=sys.stderr)
        return True


def main():
    app = M20TrayApp()
    Gtk.main()


if __name__ == "__main__":
    main()
