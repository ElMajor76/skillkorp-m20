#!/usr/bin/env python3
"""
SkillKorp M20 Ultimate - Multi-Profile Manager & Auto-Switching
Manages persistent mouse profiles and automatic switching based on active applications.
"""

import os
import sys
import json
import shutil
import subprocess
import re
from typing import Dict, List, Optional, Any

CONFIG_DIR = os.path.expanduser("~/.config/skillkorp-m20")
PROFILES_DIR = os.path.join(CONFIG_DIR, "profiles")
STATE_FILE = os.path.join(CONFIG_DIR, "profile_state.json")
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
        with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)

# Default profiles created on initial setup
DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {
        "id": "default",
        "name": "Par défaut",
        "description": "Profil polyvalent pour usage quotidien",
        "dpi_stages": [400, 800, 1600, 3200, 6400, 26000],
        "active_stage": 2,
        "polling_rate": 1000,
        "lod": 1,
        "debounce": 4,
        "motion_sync": True,
        "angle_snap": False,
        "ripple": False,
        "sleep_timer_minutes": 5,
        "move_to_wake": True,
        "buttons": {
            "1": "left_click",
            "2": "right_click",
            "3": "middle_click",
            "4": "forward",
            "5": "backward",
        },
        "auto_switch_apps": [],
    },
    "gaming_fps": {
        "id": "gaming_fps",
        "name": "Gaming FPS",
        "description": "Optimisé pour CS2, Valorant, Apex (1000Hz, 800 DPI, LOD 1mm)",
        "dpi_stages": [400, 800, 1600, 3200],
        "active_stage": 2,
        "polling_rate": 1000,
        "lod": 1,
        "debounce": 2,
        "motion_sync": True,
        "angle_snap": False,
        "ripple": False,
        "sleep_timer_minutes": 10,
        "move_to_wake": True,
        "buttons": {
            "1": "left_click",
            "2": "right_click",
            "3": "middle_click",
            "4": "forward",
            "5": "backward",
        },
        "auto_switch_apps": [
            "cs2",
            "csgo_linux64",
            "valorant",
            "apex",
            "tf2",
            "hl2_linux",
            "steam_app",
            "lutris",
            "heroic",
        ],
    },
    "office_economy": {
        "id": "office_economy",
        "name": "Bureautique & Autonomie",
        "description": "Économie de batterie maximale (250Hz, raccourcis Copier/Coller)",
        "dpi_stages": [800, 1200, 1600],
        "active_stage": 2,
        "polling_rate": 250,
        "lod": 2,
        "debounce": 8,
        "motion_sync": False,
        "angle_snap": False,
        "ripple": False,
        "sleep_timer_minutes": 3,
        "move_to_wake": False,
        "buttons": {
            "1": "left_click",
            "2": "right_click",
            "3": "middle_click",
            "4": "copy",
            "5": "paste",
        },
        "auto_switch_apps": [
            "code",
            "firefox",
            "google-chrome",
            "chromium",
            "soffice.bin",
            "libreoffice",
            "blender",
            "gimp",
            "inkscape",
        ],
    },
}


class ProfileManager:
    def __init__(self, profiles_dir: str = PROFILES_DIR, state_file: str = STATE_FILE):
        self.profiles_dir = profiles_dir
        self.state_file = state_file
        self._ensure_init()

    def _ensure_init(self):
        os.makedirs(self.profiles_dir, exist_ok=True)
        # Populate defaults if missing
        for prof_id, prof_data in DEFAULT_PROFILES.items():
            path = self._get_profile_path(prof_id)
            if not os.path.exists(path):
                self._save_profile_file(path, prof_data)

        if not os.path.exists(self.state_file):
            self._save_state({"active_profile": "default", "auto_switch_enabled": True})

    def _get_profile_path(self, prof_id: str) -> str:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", prof_id)
        return os.path.join(self.profiles_dir, f"{safe_id}.json")

    def _save_profile_file(self, path: str, data: Dict[str, Any]):
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"active_profile": "default", "auto_switch_enabled": True}

    def _save_state(self, state: Dict[str, Any]):
        tmp_path = self.state_file + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self.state_file)

    def is_auto_switch_enabled(self) -> bool:
        return bool(self._load_state().get("auto_switch_enabled", True))

    def set_auto_switch_enabled(self, enabled: bool):
        st = self._load_state()
        st["auto_switch_enabled"] = bool(enabled)
        self._save_state(st)

    def get_active_profile_id(self) -> str:
        state = self._load_state()
        active_id = state.get("active_profile", "default")
        if not os.path.exists(self._get_profile_path(active_id)):
            return "default"
        return active_id

    def list_profiles(self) -> List[Dict[str, Any]]:
        active_id = self.get_active_profile_id()
        profiles = []
        if os.path.exists(self.profiles_dir):
            for fname in sorted(os.listdir(self.profiles_dir)):
                if fname.endswith(".json"):
                    prof_id = fname[:-5]
                    prof = self.get_profile(prof_id)
                    if prof:
                        prof["active"] = (prof_id == active_id)
                        profiles.append(prof)
        return profiles

    def get_profile(self, prof_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_profile_path(prof_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["id"] = prof_id
                return data
        except Exception as e:
            print(f"[ProfileManager] Erreur chargement {path}: {e}", file=sys.stderr)
            return None

    def save_profile(self, prof_id: str, data: Dict[str, Any]):
        path = self._get_profile_path(prof_id)
        data["id"] = prof_id
        self._save_profile_file(path, data)

    def create_profile(self, prof_id: str, name: str, copy_from: Optional[str] = None) -> Dict[str, Any]:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", prof_id).lower()
        if copy_from:
            source = self.get_profile(copy_from)
        else:
            source = self.get_profile("default")

        if not source:
            source = DEFAULT_PROFILES["default"].copy()

        new_data = json.loads(json.dumps(source))
        new_data["id"] = safe_id
        new_data["name"] = name
        new_data["description"] = f"Profil personnalisé : {name}"
        new_data["auto_switch_apps"] = []
        self.save_profile(safe_id, new_data)
        return new_data

    def delete_profile(self, prof_id: str) -> bool:
        if prof_id == "default":
            raise ValueError("Le profil 'default' ne peut pas être supprimé.")
        path = self._get_profile_path(prof_id)
        if os.path.exists(path):
            os.remove(path)
            if self.get_active_profile_id() == prof_id:
                self.switch_profile("default")
            return True
        return False

    def export_profile(self, prof_id: str, target_file: str) -> bool:
        prof = self.get_profile(prof_id)
        if not prof:
            raise ValueError(f"Profil '{prof_id}' introuvable.")
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(prof, f, indent=2, ensure_ascii=False)
        return True

    def import_profile(self, source_file: str, new_id: Optional[str] = None) -> str:
        with open(source_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        prof_id = new_id or data.get("id") or os.path.basename(source_file).replace(".json", "")
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", prof_id).lower()
        data["id"] = safe_id
        self.save_profile(safe_id, data)
        return safe_id

    def switch_profile(self, prof_id: str, driver: Optional[Any] = None) -> Dict[str, Any]:
        prof = self.get_profile(prof_id)
        if not prof:
            raise ValueError(f"Profil '{prof_id}' introuvable.")

        # Update active state
        st = self._load_state()
        st["active_profile"] = prof_id
        self._save_state(st)

        # Apply settings to driver and hardware if driver is provided
        if driver is not None:
            self.apply_profile_to_driver(prof, driver)

        return prof

    def apply_profile_to_driver(self, prof: Dict[str, Any], driver: Any):
        """Applies profile configuration parameters directly to driver and hardware."""
        # 1. Update DPI & Sensor
        driver.set_dpi_and_sensor(
            stages=prof.get("dpi_stages"),
            active_stage=prof.get("active_stage"),
            lod=prof.get("lod"),
            debounce=prof.get("debounce"),
            motion_sync=prof.get("motion_sync"),
            angle_snap=prof.get("angle_snap"),
            ripple=prof.get("ripple"),
        )
        # 2. Polling rate
        if "polling_rate" in prof:
            driver.set_polling_rate(prof["polling_rate"])

        # 3. Button remap
        if "buttons" in prof:
            driver.set_buttons({int(k): v for k, v in prof["buttons"].items()})

        # 4. Power & Sleep settings
        sleep_min = prof.get("sleep_timer_minutes", 5)
        move_wake = prof.get("move_to_wake", True)
        if hasattr(driver, "set_power_settings"):
            driver.set_power_settings(sleep_timer_minutes=sleep_min, move_to_wake=move_wake)


def detect_active_window_class() -> Optional[str]:
    """Detects active window process name or WM_CLASS on Linux (X11 & Wayland)."""
    # 1. Try xdotool (fastest on X11 / XWayland)
    try:
        out = subprocess.check_output(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.3,
        ).strip()
        if out:
            return out.lower()
    except Exception:
        pass

    # 2. Try xprop
    try:
        out = subprocess.check_output(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.3,
        ).strip()
        win_id = out.split()[-1]
        if win_id and win_id != "0x0":
            prop_out = subprocess.check_output(
                ["xprop", "-id", win_id, "WM_CLASS"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=0.3,
            ).strip()
            # WM_CLASS(STRING) = "code", "Code"
            matches = re.findall(r'"([^"]+)"', prop_out)
            if matches:
                return matches[-1].lower()
    except Exception:
        pass

    return None
