"""
Tests unitaires pour le module m20_driver.py
Couvre les buffers HID, checksums, constantes et validations.
"""

import sys
import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Ajouter le répertoire racine au PYTHONPATH pour importer m20_driver
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import m20_driver
from m20_driver import (
    POLLING_RATE_MAP,
    LIGHT_MODES,
    BUTTON_ACTIONS,
    PHYSICAL_BTN_TO_SLOT,
    SkillkorpM20Driver,
    _HIDIOCSFEATURE,
)


class TestHidiocsMacro(unittest.TestCase):
    """Tests du calcul ioctl HIDIOCSFEATURE."""

    def test_hidiocsfeature_9bytes(self):
        """Report ID 0x06 polling rate: 9 bytes."""
        result = _HIDIOCSFEATURE(9)
        # Doit être un entier positif de 32 bits
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)
        # Vérifier la structure: (3 << 30) | (9 << 16) | (ord('H') << 8) | 0x06
        expected = (3 << 30) | (9 << 16) | (ord('H') << 8) | 0x06
        self.assertEqual(result, expected)

    def test_hidiocsfeature_56bytes(self):
        """Report ID 0x04 DPI sensor: 56 bytes."""
        result = _HIDIOCSFEATURE(56)
        expected = (3 << 30) | (56 << 16) | (ord('H') << 8) | 0x06
        self.assertEqual(result, expected)

    def test_hidiocsfeature_15bytes(self):
        """Report ID 0x05 lighting/power: 15 bytes."""
        result = _HIDIOCSFEATURE(15)
        expected = (3 << 30) | (15 << 16) | (ord('H') << 8) | 0x06
        self.assertEqual(result, expected)


class TestConstants(unittest.TestCase):
    """Tests des constantes du driver."""

    def test_polling_rate_map_keys(self):
        """POLLING_RATE_MAP doit contenir exactement 125, 250, 500, 1000."""
        self.assertEqual(set(POLLING_RATE_MAP.keys()), {125, 250, 500, 1000})

    def test_polling_rate_map_complement(self):
        """interval + not_interval doit valoir 0xFF pour chaque taux."""
        for rate, info in POLLING_RATE_MAP.items():
            self.assertEqual(
                info["interval"] + info["not_interval"], 0xFF,
                f"Complément incorrect pour {rate} Hz"
            )

    def test_light_modes_structure(self):
        """LIGHT_MODES: chaque entrée est (key, label, id); IDs uniques."""
        ids = [m[2] for m in LIGHT_MODES]
        self.assertEqual(len(ids), len(set(ids)), "IDs de modes RGB en double")
        for mode in LIGHT_MODES:
            self.assertEqual(len(mode), 3)
            self.assertIsInstance(mode[0], str)  # key
            self.assertIsInstance(mode[1], str)  # label
            self.assertIsInstance(mode[2], int)  # id

    def test_button_actions_structure(self):
        """BUTTON_ACTIONS: chaque action a (label, b0, b1, b2)."""
        for key, val in BUTTON_ACTIONS.items():
            self.assertEqual(len(val), 4, f"Action '{key}' mal formée")
            self.assertIsInstance(val[0], str)
            for byte_val in val[1:]:
                self.assertGreaterEqual(byte_val, 0)
                self.assertLessEqual(byte_val, 0xFF)

    def test_physical_btn_to_slot_keys(self):
        """PHYSICAL_BTN_TO_SLOT doit couvrir les boutons 1 à 6."""
        self.assertEqual(set(PHYSICAL_BTN_TO_SLOT.keys()), {1, 2, 3, 4, 5, 6})

    def test_physical_btn_to_slot_slots_in_range(self):
        """Tous les slots doivent être dans 0..17 (18 slots firmware)."""
        for btn, slot in PHYSICAL_BTN_TO_SLOT.items():
            self.assertGreaterEqual(slot, 0)
            self.assertLessEqual(slot, 17, f"Slot {slot} du bouton {btn} hors limites")


class TestReport0x05Checksum(unittest.TestCase):
    """Tests du buffer et checksum du Report 0x05 (éclairage + veille)."""

    def _make_driver(self, config=None):
        """Crée un driver avec un config minimal sans accès HID."""
        default_config = {
            "light_mode": "static",
            "brightness": 8,
            "speed": 4,
            "light_color": [255, 0, 0],
            "sleep_timer_minutes": 5,
            "move_to_wake": True,
            "polling_rate": 1000,
            "dpi_stages": [800, 1600, 3200],
            "active_stage": 2,
            "lod": 1,
            "debounce": 4,
            "ripple": False,
            "angle_snap": False,
            "motion_sync": True,
            "buttons": {"1": "left_click", "2": "right_click"},
            "battery": 100,
            "charging": False,
        }
        if config:
            default_config.update(config)
        with patch.object(SkillkorpM20Driver, "_load_or_default_config", return_value=default_config):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver.__new__(SkillkorpM20Driver)
                driver.dev_path = None
                driver.config = default_config
                driver._config_mtime = os.path.getmtime(m20_driver.DEFAULT_PROFILE_FILE) if os.path.exists(m20_driver.DEFAULT_PROFILE_FILE) else 0.0
        return driver

    def _call_lighting_report(self, driver, **kwargs):
        """Intercepte le buffer envoyé par _send_lighting_and_power_report."""
        captured = []
        real_send = m20_driver.SkillkorpM20Driver._send_feature_report

        def mock_send(self, buf, retries=3):
            captured.append(bytes(buf))
            return True

        with patch.object(SkillkorpM20Driver, "_send_feature_report", mock_send):
            driver._send_lighting_and_power_report(**kwargs)

        self.assertTrue(captured, "Aucun buffer envoyé")
        return captured[0]

    def test_report_id_and_length(self):
        """buf[0]=0x05, buf[1]=0x0F pour tout appel lighting_and_power."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver,
            mode="static",
            brightness=8,
            speed=4,
            color=(255, 0, 0),
            sleep_timer_minutes=5,
            move_to_wake=True,
        )
        self.assertEqual(buf[0], 0x05, "Report ID incorrect")
        self.assertEqual(buf[1], 0x0F, "Longueur incorrecte (attendu 15)")

    def test_profile_index(self):
        """buf[2] doit être 0x01 (index de profil)."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver,
            mode="static",
            brightness=8,
            speed=4,
            color=(255, 0, 0),
            sleep_timer_minutes=5,
            move_to_wake=True,
        )
        self.assertEqual(buf[2], 0x01)

    def test_checksum_static_red(self):
        """Checksum = sum(buf[3:11]) & 0xFFFF, stocké en big-endian aux octets 11-12."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver,
            mode="static",
            brightness=8,
            speed=4,
            color=(255, 0, 0),
            sleep_timer_minutes=5,
            move_to_wake=True,
        )
        csum_expected = sum(buf[3:11]) & 0xFFFF
        csum_actual = (buf[11] << 8) | buf[12]
        self.assertEqual(csum_actual, csum_expected,
                         f"Checksum incorrect: buf={buf.hex()}")

    def test_checksum_breathing_blue(self):
        """Vérifie le checksum avec mode breathing et couleur bleue."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver,
            mode="breathing",
            brightness=4,
            speed=6,
            color=(0, 0, 255),
            sleep_timer_minutes=10,
            move_to_wake=False,
        )
        csum_expected = sum(buf[3:11]) & 0xFFFF
        csum_actual = (buf[11] << 8) | buf[12]
        self.assertEqual(csum_actual, csum_expected)

    def test_sleep_timer_byte(self):
        """buf[9] doit contenir la valeur du délai de veille en minutes."""
        driver = self._make_driver()
        for minutes in [1, 5, 30, 60]:
            buf = self._call_lighting_report(
                driver,
                mode="static",
                brightness=8,
                speed=4,
                color=(255, 255, 255),
                sleep_timer_minutes=minutes,
                move_to_wake=True,
            )
            self.assertEqual(buf[9], minutes, f"sleep_timer {minutes} min mal encodé")

    def test_move_to_wake_encoding(self):
        """buf[10]=0x00 si move_to_wake=True, 0x01 si False."""
        driver = self._make_driver()
        buf_move = self._call_lighting_report(
            driver, mode="static", brightness=8, speed=4,
            color=(255, 0, 0), sleep_timer_minutes=5, move_to_wake=True,
        )
        self.assertEqual(buf_move[10], 0x00, "move_to_wake=True doit encoder 0x00")

        buf_click = self._call_lighting_report(
            driver, mode="static", brightness=8, speed=4,
            color=(255, 0, 0), sleep_timer_minutes=5, move_to_wake=False,
        )
        self.assertEqual(buf_click[10], 0x01, "move_to_wake=False doit encoder 0x01")

    def test_rgb_color_bytes(self):
        """buf[6], buf[7], buf[8] doivent contenir R, G, B."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver, mode="static", brightness=8, speed=4,
            color=(123, 200, 42), sleep_timer_minutes=5, move_to_wake=True,
        )
        self.assertEqual(buf[6], 123)
        self.assertEqual(buf[7], 200)
        self.assertEqual(buf[8], 42)

    def test_brightness_speed_packing(self):
        """buf[4] = (brightness << 4) | speed (nibbles)."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver, mode="static", brightness=5, speed=3,
            color=(0, 0, 0), sleep_timer_minutes=5, move_to_wake=True,
        )
        expected = ((5 & 0x0F) << 4) | (3 & 0x0F)
        self.assertEqual(buf[4], expected)

    def test_mode_id_static(self):
        """mode 'static' → mode_id=2 → buf[3] = (2 << 4) & 0xF0 = 0x20."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver, mode="static", brightness=8, speed=4,
            color=(255, 0, 0), sleep_timer_minutes=5, move_to_wake=True,
        )
        self.assertEqual(buf[3], 0x20)

    def test_mode_id_breathing(self):
        """mode 'breathing' → mode_id=3 → buf[3] = 0x30."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver, mode="breathing", brightness=8, speed=4,
            color=(255, 0, 0), sleep_timer_minutes=5, move_to_wake=True,
        )
        self.assertEqual(buf[3], 0x30)

    def test_buffer_length(self):
        """Le buffer envoyé doit faire exactement 15 octets."""
        driver = self._make_driver()
        buf = self._call_lighting_report(
            driver, mode="static", brightness=8, speed=4,
            color=(255, 0, 0), sleep_timer_minutes=5, move_to_wake=True,
        )
        self.assertEqual(len(buf), 15)


class TestReport0x04DPI(unittest.TestCase):
    """Tests du buffer Report 0x04 (DPI + capteur)."""

    def _make_driver_and_capture(self, stages, active_stage=1):
        """Capture le buffer envoyé lors d'un set_dpi_and_sensor."""
        config = {
            "polling_rate": 1000,
            "dpi_stages": stages,
            "active_stage": active_stage,
            "lod": 1,
            "debounce": 4,
            "ripple": False,
            "angle_snap": False,
            "motion_sync": True,
            "light_mode": "static",
            "brightness": 8,
            "speed": 4,
            "light_color": [255, 0, 0],
            "sleep_timer_minutes": 5,
            "move_to_wake": True,
            "buttons": {},
            "battery": 100,
            "charging": False,
        }
        with patch.object(SkillkorpM20Driver, "_load_or_default_config", return_value=config):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver.__new__(SkillkorpM20Driver)
                driver.dev_path = None
                driver.config = config.copy()
                driver._config_mtime = os.path.getmtime(m20_driver.DEFAULT_PROFILE_FILE) if os.path.exists(m20_driver.DEFAULT_PROFILE_FILE) else 0.0

        captured = []

        def mock_send(self, buf, retries=3):
            captured.append(bytes(buf))
            return True

        with patch.object(SkillkorpM20Driver, "_send_feature_report", mock_send):
            with patch.object(SkillkorpM20Driver, "_save_config"):
                driver.set_dpi_and_sensor(stages=stages, active_stage=active_stage)

        return captured[0] if captured else None

    def test_report_id_0x04(self):
        buf = self._make_driver_and_capture([800, 1600], active_stage=1)
        self.assertIsNotNone(buf)
        self.assertEqual(buf[0], 0x04)

    def test_dpi_encoding_800(self):
        """800 DPI → enc = (800 // 50) - 1 = 15 = 0x0F."""
        buf = self._make_driver_and_capture([800], active_stage=1)
        self.assertIsNotNone(buf)
        enc = (800 // 50) - 1
        self.assertEqual(buf[8], enc & 0xFF)
        self.assertEqual(buf[16], (enc >> 8) & 0xFF)

    def test_dpi_encoding_26000(self):
        """26000 DPI → enc = (26000 // 50) - 1 = 519 = 0x207."""
        buf = self._make_driver_and_capture([26000], active_stage=1)
        self.assertIsNotNone(buf)
        enc = (26000 // 50) - 1  # 519
        self.assertEqual(buf[8], enc & 0xFF)     # 0x07
        self.assertEqual(buf[16], (enc >> 8) & 0xFF)  # 0x02

    def test_active_stage_byte(self):
        """buf[24] doit contenir l'étape active (1-indexée)."""
        buf = self._make_driver_and_capture([400, 800, 1600], active_stage=2)
        self.assertIsNotNone(buf)
        self.assertEqual(buf[24], 2)

    def test_stages_mask(self):
        """buf[5] = (1 << N) - 1 pour N étapes activées."""
        for n in range(1, 7):
            stages = [800] * n
            buf = self._make_driver_and_capture(stages, active_stage=1)
            expected_mask = (1 << n) - 1
            self.assertEqual(buf[5], expected_mask, f"Masque incorrect pour {n} étapes")


class TestQueryStatusClamp(unittest.TestCase):
    """Tests du clamp active_stage dans query_status."""

    def _make_driver_with_config(self, config):
        with patch.object(SkillkorpM20Driver, "_load_or_default_config", return_value=config):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver.__new__(SkillkorpM20Driver)
                driver.dev_path = None
                driver.config = config.copy()
                driver._config_mtime = os.path.getmtime(m20_driver.DEFAULT_PROFILE_FILE) if os.path.exists(m20_driver.DEFAULT_PROFILE_FILE) else 0.0
        return driver

    def test_active_stage_clamped_when_out_of_bounds(self):
        """Si active_stage > len(dpi_stages), query_status ne doit pas lever IndexError."""
        config = {
            "polling_rate": 1000,
            "dpi_stages": [800, 1600],  # 2 étapes
            "active_stage": 5,          # hors limites !
            "lod": 1, "debounce": 4, "ripple": False, "angle_snap": False,
            "motion_sync": True, "light_mode": "static", "brightness": 8,
            "speed": 4, "light_color": [255, 0, 0], "sleep_timer_minutes": 5,
            "move_to_wake": True, "buttons": {}, "battery": 100, "charging": False,
        }
        driver = self._make_driver_with_config(config)
        with patch.object(driver, "is_connected", return_value=False):
            with patch.object(driver, "_read_input_reports", return_value=[]):
                # Ne doit PAS lever d'exception
                status = driver.query_status()
                self.assertIsNotNone(status)
                # active_dpi doit pointer sur une étape valide
                stages = config["dpi_stages"]
                self.assertIn(status["active_dpi"], stages)

    def test_active_stage_1_is_valid(self):
        """active_stage=1 (minimum) doit retourner le premier DPI."""
        config = {
            "polling_rate": 1000,
            "dpi_stages": [400, 800],
            "active_stage": 1,
            "lod": 1, "debounce": 4, "ripple": False, "angle_snap": False,
            "motion_sync": True, "light_mode": "static", "brightness": 8,
            "speed": 4, "light_color": [255, 0, 0], "sleep_timer_minutes": 5,
            "move_to_wake": True, "buttons": {}, "battery": 100, "charging": False,
        }
        driver = self._make_driver_with_config(config)
        with patch.object(driver, "is_connected", return_value=False):
            with patch.object(driver, "_read_input_reports", return_value=[]):
                status = driver.query_status()
                self.assertEqual(status["active_dpi"], 400)


class TestSetButtonsSlotMapping(unittest.TestCase):
    """Tests du mappage boutons physiques → slots firmware (Report 0x08)."""

    def _make_driver(self):
        config = {
            "polling_rate": 1000,
            "dpi_stages": [800],
            "active_stage": 1,
            "lod": 1, "debounce": 4, "ripple": False, "angle_snap": False,
            "motion_sync": True, "light_mode": "static", "brightness": 8,
            "speed": 4, "light_color": [255, 0, 0], "sleep_timer_minutes": 5,
            "move_to_wake": True, "buttons": {}, "battery": 100, "charging": False,
        }
        with patch.object(SkillkorpM20Driver, "_load_or_default_config", return_value=config):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver.__new__(SkillkorpM20Driver)
                driver.dev_path = None
                driver.config = config.copy()
                driver._config_mtime = os.path.getmtime(m20_driver.DEFAULT_PROFILE_FILE) if os.path.exists(m20_driver.DEFAULT_PROFILE_FILE) else 0.0
        return driver

    def test_set_buttons_report_id(self):
        """Le buffer set_buttons doit commencer par 0x08."""
        driver = self._make_driver()
        captured = []

        def mock_send(self, buf, retries=3):
            captured.append(bytes(buf))
            return True

        with patch.object(SkillkorpM20Driver, "_send_feature_report", mock_send):
            with patch.object(SkillkorpM20Driver, "_save_config"):
                driver.set_buttons({1: "left_click", 2: "right_click"})

        self.assertTrue(captured)
        self.assertEqual(captured[0][0], 0x08)

    def test_physical_btn_slot_mapping(self):
        """Vérifie que les slots physiques sont aux bons offsets dans le buffer."""
        driver = self._make_driver()
        captured = []

        def mock_send(self, buf, retries=3):
            captured.append(bytes(buf))
            return True

        with patch.object(SkillkorpM20Driver, "_send_feature_report", mock_send):
            with patch.object(SkillkorpM20Driver, "_save_config"):
                driver.set_buttons({
                    1: "left_click",    # Slot 0
                    2: "right_click",   # Slot 1
                    6: "dpi_cycle",     # Slot 3
                })

        self.assertTrue(captured)
        buf = captured[0]
        # Buffer format: buf[0]=0x08, buf[1]=0x3B, buf[2]=0x01
        # Slots: 3 bytes each (b_type, b_code, b_mod) starting at offset 3
        # Slot 3 (bouton 6 DPI) → offset 3 + 3*3 = 12
        dpi_code = BUTTON_ACTIONS["dpi_cycle"][1]
        slot3_offset = 3 + 3 * 3  # = 12
        self.assertEqual(buf[slot3_offset], dpi_code,
                         f"Bouton 6 (Slot 3) devrait avoir code {dpi_code:#04x}, buf={buf.hex()}")


class TestProfileValidation(unittest.TestCase):
    """Tests de la validation dans import_profile (Bug 9)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from profile_manager import ProfileManager
        self.pm = ProfileManager(
            profiles_dir=os.path.join(self.tmpdir, "profiles"),
            state_file=os.path.join(self.tmpdir, "state.json"),
        )

    def _write_profile_file(self, data):
        path = os.path.join(self.tmpdir, "test_import.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_valid_profile_imports_ok(self):
        """Un profil valide doit s'importer sans erreur."""
        data = {
            "id": "test",
            "name": "Test",
            "dpi_stages": [800, 1600],
            "active_stage": 1,
            "polling_rate": 1000,
            "buttons": {"1": "left_click", "2": "right_click"},
        }
        path = self._write_profile_file(data)
        result_id = self.pm.import_profile(path)
        self.assertEqual(result_id, "test")

    def test_invalid_dpi_raises(self):
        """Un DPI hors limites doit lever ValueError."""
        data = {"dpi_stages": [100000], "buttons": {}}
        path = self._write_profile_file(data)
        with self.assertRaises(ValueError):
            self.pm.import_profile(path)

    def test_invalid_polling_rate_raises(self):
        """Un polling rate non standard doit lever ValueError."""
        data = {"polling_rate": 750, "buttons": {}}
        path = self._write_profile_file(data)
        with self.assertRaises(ValueError):
            self.pm.import_profile(path)

    def test_invalid_button_action_raises(self):
        """Une action inconnue doit lever ValueError."""
        data = {"buttons": {"1": "teleport"}}
        path = self._write_profile_file(data)
        with self.assertRaises(ValueError):
            self.pm.import_profile(path)

    def test_invalid_button_number_raises(self):
        """Un numéro de bouton invalide (> 6) doit lever ValueError."""
        data = {"buttons": {"9": "left_click"}}
        path = self._write_profile_file(data)
        with self.assertRaises(ValueError):
            self.pm.import_profile(path)

    def test_invalid_active_stage_raises(self):
        """active_stage hors limites doit lever ValueError."""
        data = {"dpi_stages": [800, 1600], "active_stage": 5, "buttons": {}}
        path = self._write_profile_file(data)
        with self.assertRaises(ValueError):
            self.pm.import_profile(path)

    def test_dpi_too_many_stages_raises(self):
        """Plus de 8 étapes DPI doit lever ValueError."""
        data = {"dpi_stages": [800] * 9, "buttons": {}}
        path = self._write_profile_file(data)
        with self.assertRaises(ValueError):
            self.pm.import_profile(path)


class TestDefaultProfilesHaveRGBFields(unittest.TestCase):
    """Vérifie que DEFAULT_PROFILES contient bien les champs RGB."""

    def test_all_defaults_have_light_fields(self):
        from profile_manager import DEFAULT_PROFILES
        required = {"light_mode", "brightness", "speed", "light_color"}
        for prof_id, prof in DEFAULT_PROFILES.items():
            for field in required:
                self.assertIn(field, prof,
                              f"DEFAULT_PROFILES['{prof_id}'] manque le champ '{field}'")

    def test_light_color_is_rgb_list(self):
        from profile_manager import DEFAULT_PROFILES
        for prof_id, prof in DEFAULT_PROFILES.items():
            color = prof.get("light_color")
            self.assertIsInstance(color, list, f"light_color de '{prof_id}' n'est pas une liste")
            self.assertEqual(len(color), 3, f"light_color de '{prof_id}' n'a pas 3 composantes")
            for c in color:
                self.assertGreaterEqual(c, 0)
                self.assertLessEqual(c, 255)


class TestReloadConfigIfChanged(unittest.TestCase):
    """Tests du rechargement conditionnel de configuration multi-processus."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "default.json")
        self.initial_config = {
            "polling_rate": 500,
            "dpi_stages": [800, 1600],
            "active_stage": 1,
            "light_mode": "static",
            "brightness": 5,
            "speed": 3,
            "light_color": [255, 0, 0],
            "sleep_timer_minutes": 5,
            "move_to_wake": True,
            "buttons": {"1": "left_click"},
            "battery": 80,
            "charging": False,
        }
        with open(self.config_path, "w") as f:
            json.dump(self.initial_config, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reload_when_file_modified(self):
        """Si le fichier change sur le disque, reload_config_if_changed recharge et renvoie True."""
        with patch("m20_driver.DEFAULT_PROFILE_FILE", self.config_path):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver()
                self.assertEqual(driver.config.get("polling_rate"), 500)

                # Pas de modification : renvoie False
                self.assertFalse(driver.reload_config_if_changed())

                # Modification externe du fichier (en changeant aussi mtime explicitement)
                updated_config = self.initial_config.copy()
                updated_config["polling_rate"] = 1000
                with open(self.config_path, "w") as f:
                    json.dump(updated_config, f)
                new_mtime = os.path.getmtime(self.config_path) + 10.0
                os.utime(self.config_path, (new_mtime, new_mtime))

                # Le rechargement doit détecter le nouveau mtime et mettre à jour self.config
                reloaded = driver.reload_config_if_changed()
                self.assertTrue(reloaded)
                self.assertEqual(driver.config.get("polling_rate"), 1000)

    def test_reload_when_file_unchanged(self):
        """Si le fichier n'a pas bougé, reload_config_if_changed renvoie False."""
        with patch("m20_driver.DEFAULT_PROFILE_FILE", self.config_path):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver()
                self.assertFalse(driver.reload_config_if_changed())

    def test_reload_when_file_missing(self):
        """Si le fichier n'existe pas, reload_config_if_changed renvoie False sans crash."""
        missing_path = os.path.join(self.temp_dir.name, "nonexistent.json")
        with patch("m20_driver.DEFAULT_PROFILE_FILE", missing_path):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver()
                self.assertFalse(driver.reload_config_if_changed())

    def test_query_status_triggers_reload(self):
        """query_status recharge automatiquement la configuration si modifiée sur le disque."""
        with patch("m20_driver.DEFAULT_PROFILE_FILE", self.config_path):
            with patch.object(SkillkorpM20Driver, "find_device", return_value=None):
                driver = SkillkorpM20Driver()
                with patch.object(driver, "is_connected", return_value=False):
                    status = driver.query_status()
                    self.assertEqual(status["polling_rate_hz"], 500)

                    # Modifier le fichier externe
                    updated_config = self.initial_config.copy()
                    updated_config["polling_rate"] = 1000
                    with open(self.config_path, "w") as f:
                        json.dump(updated_config, f)
                    new_mtime = os.path.getmtime(self.config_path) + 10.0
                    os.utime(self.config_path, (new_mtime, new_mtime))

                    # query_status doit refléter la nouvelle config
                    status = driver.query_status()
                    self.assertEqual(status["polling_rate_hz"], 1000)


if __name__ == "__main__":
    unittest.main()
