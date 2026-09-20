#!/usr/bin/env python3
"""
SkillKorp M20 Ultimate - Application Graphique Linux (GTK 4 / Libadwaita)
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from m20_driver import SkillkorpM20Driver, BUTTON_ACTIONS, POLLING_RATE_MAP

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib


class SkillkorpM20Window(Adw.PreferencesWindow):
    def __init__(self, app):
        super().__init__(application=app, title="SkillKorp M20 Ultimate")
        self.set_default_size(780, 680)

        self.driver = SkillkorpM20Driver()
        self._syncing_from_hardware = False

        # Build UI pages
        self._init_dpi_page()
        self._init_buttons_page()
        self._init_power_page()

        # Add HeaderBar widgets
        self._init_header_bar()

        # Refresh status periodically (every 1 second)
        GLib.timeout_add_seconds(1, self._periodic_refresh)

    def _init_header_bar(self):
        self.conn_label = Gtk.Label(label="Connectée")
        self.conn_label.add_css_class("success")
        self.bat_label = Gtk.Label(label="🔋 100%")
        pass

    def _on_apply_all_clicked(self, button=None):
        self._on_apply_dpi_clicked()
        time.sleep(0.3)
        self._on_apply_buttons_clicked()
        time.sleep(0.3)
        self._on_apply_power_clicked()

    def _init_dpi_page(self):
        page = Adw.PreferencesPage(title="DPI & Capteur", icon_name="input-mouse-symbolic")
        self.add(page)

        # Group: DPI Stages
        dpi_group = Adw.PreferencesGroup(title="Étapes de Sensibilité (DPI)", description="Capteur PixArt PAW3395 (50 à 26 000 DPI)")
        page.add(dpi_group)

        stages = self.driver.config.get("dpi_stages", [400, 800, 1600, 3200, 6400, 26000])
        active_idx = self.driver.config.get("active_stage", 2)

        self.stage_spinners = []
        self.stage_radios = []
        first_radio = None

        for i in range(6):
            val = stages[i] if i < len(stages) else 800
            row = Adw.ActionRow(title=f"Étape {i+1}")

            # Radio button to select active stage
            radio = Gtk.CheckButton(label="Actif")
            if first_radio is None:
                first_radio = radio
            else:
                radio.set_group(first_radio)

            if (i + 1) == active_idx:
                radio.set_active(True)

            radio.connect("toggled", self._on_stage_radio_toggled, i + 1)
            self.stage_radios.append(radio)
            row.add_prefix(radio)

            # SpinButton for DPI (50 to 26000, step 50)
            adjustment = Gtk.Adjustment(value=val, lower=50, upper=26000, step_increment=50, page_increment=500)
            spin = Gtk.SpinButton(adjustment=adjustment, numeric=True)
            spin.set_valign(Gtk.Align.CENTER)
            self.stage_spinners.append(spin)
            row.add_suffix(spin)

            dpi_group.add(row)

        # Group: Sensor Settings
        sensor_group = Adw.PreferencesGroup(title="Paramètres Avancés du Capteur")
        page.add(sensor_group)

        # LOD
        self.lod_row = Adw.ComboRow(title="Distance de levée (LOD)", subtitle="Hauteur de coupure du capteur optique")
        self.lod_row.set_model(Gtk.StringList.new(["1 mm (Bas)", "2 mm (Haut)"]))
        cur_lod = self.driver.config.get("lod", 1)
        self.lod_row.set_selected(0 if cur_lod <= 1 else 1)
        sensor_group.add(self.lod_row)

        # Debounce
        cur_deb = self.driver.config.get("debounce", 4)
        deb_adj = Gtk.Adjustment(value=cur_deb, lower=0, upper=20, step_increment=1, page_increment=2)
        self.debounce_row = Adw.SpinRow(title="Temps de réponse touches (Debounce)", subtitle="Anti-rebond matériel des switches", adjustment=deb_adj)
        sensor_group.add(self.debounce_row)

        # Motion Sync
        self.msync_row = Adw.SwitchRow(title="Synchronisation du mouvement (Motion Sync)", subtitle="Synchronise les données du capteur aux requêtes USB")
        self.msync_row.set_active(self.driver.config.get("motion_sync", True))
        sensor_group.add(self.msync_row)

        # Angle Snapping
        self.angle_row = Adw.SwitchRow(title="Correction en ligne droite (Angle Snapping)", subtitle="Aide à tracer des lignes droites parfaites")
        self.angle_row.set_active(self.driver.config.get("angle_snap", False))
        sensor_group.add(self.angle_row)

        # Ripple Control
        self.ripple_row = Adw.SwitchRow(title="Contrôle des ondulations (Ripple Control)", subtitle="Lissage des tremblements à haut DPI")
        self.ripple_row.set_active(self.driver.config.get("ripple", False))
        sensor_group.add(self.ripple_row)

        # Apply button row
        apply_group = Adw.PreferencesGroup()
        page.add(apply_group)
        btn = Gtk.Button(label="Enregistrer & Appliquer les paramètres DPI")
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", self._on_apply_dpi_clicked)
        apply_group.add(btn)

    def _init_buttons_page(self):
        page = Adw.PreferencesPage(title="Boutons", icon_name="input-gaming-symbolic")
        self.add(page)

        btn_group = Adw.PreferencesGroup(title="Attribution des Boutons", description="Configurer les 5 boutons physiques de la souris")
        page.add(btn_group)

        self.btn_action_keys = list(BUTTON_ACTIONS.keys())
        btn_action_labels = [info[0] for info in BUTTON_ACTIONS.values()]

        self.btn_combos = []
        button_names = [
            "Bouton 1 : Clic Gauche",
            "Bouton 2 : Clic Droit",
            "Bouton 3 : Molette (Bouton Central)",
            "Bouton 4 : Suivant (Latéral Avant)",
            "Bouton 5 : Précédent (Latéral Arrière)",
        ]
        current_buttons = self.driver.config.get("buttons", {})

        for i in range(1, 6):
            row = Adw.ComboRow(title=button_names[i - 1])
            string_list = Gtk.StringList.new(btn_action_labels)
            row.set_model(string_list)

            cur_act = current_buttons.get(str(i), "left_click" if i == 1 else "right_click" if i == 2 else "middle_click" if i == 3 else "forward" if i == 4 else "backward")
            try:
                selected_idx = self.btn_action_keys.index(cur_act)
            except ValueError:
                selected_idx = 0
            row.set_selected(selected_idx)
            self.btn_combos.append(row)
            btn_group.add(row)

        apply_group = Adw.PreferencesGroup()
        page.add(apply_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)

        btn = Gtk.Button(label="Enregistrer & Appliquer les Boutons")
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.connect("clicked", self._on_apply_buttons_clicked)
        btn_box.append(btn)

        rst_btn = Gtk.Button(label="Restaurer par Défaut")
        rst_btn.add_css_class("destructive-action")
        rst_btn.add_css_class("pill")
        rst_btn.connect("clicked", self._on_restore_buttons_clicked)
        btn_box.append(rst_btn)

        apply_group.add(btn_box)

    def _init_power_page(self):
        page = Adw.PreferencesPage(title="Alimentation & Polling", icon_name="battery-level-100-charged-symbolic")
        self.add(page)

        # Battery Group
        bat_group = Adw.PreferencesGroup(title="État de la Batterie et Veille")
        page.add(bat_group)

        self.battery_row = Adw.ActionRow(title="Batterie restante", subtitle="100% (Chargée)")
        self.bat_progress = Gtk.ProgressBar()
        self.bat_progress.set_fraction(1.0)
        self.bat_progress.set_valign(Gtk.Align.CENTER)
        self.bat_progress.set_size_request(150, -1)
        self.battery_row.add_suffix(self.bat_progress)
        bat_group.add(self.battery_row)

        # Polling Rate Group
        rate_group = Adw.PreferencesGroup(title="Taux de Scrutation (Polling Rate)", description="Fréquence de communication USB entre la souris et le PC")
        page.add(rate_group)

        self.rate_row = Adw.ComboRow(title="Fréquence de rapport USB")
        rate_options = [
            "125 Hz (Économie d'énergie - 8 ms)",
            "250 Hz (Bureautique - 4 ms)",
            "500 Hz (Gaming Standard - 2 ms)",
            "1000 Hz (E-Sports Ultra Rapide - 1 ms)",
        ]
        self.rate_row.set_model(Gtk.StringList.new(rate_options))
        cur_rate = self.driver.config.get("polling_rate", 1000)
        rate_idx = 3 if cur_rate == 1000 else 2 if cur_rate == 500 else 1 if cur_rate == 250 else 0
        self.rate_row.set_selected(rate_idx)
        rate_group.add(self.rate_row)

        apply_group = Adw.PreferencesGroup()
        page.add(apply_group)
        btn = Gtk.Button(label="Enregistrer & Appliquer les Paramètres")
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", self._on_apply_power_clicked)
        apply_group.add(btn)

    def _on_apply_dpi_clicked(self, button=None):
        try:
            stages = [int(spin.get_value()) for spin in self.stage_spinners]
            active_stage = 1
            for idx, r in enumerate(self.stage_radios):
                if r.get_active():
                    active_stage = idx + 1
                    break

            lod = 1 if self.lod_row.get_selected() == 0 else 2
            debounce = int(self.debounce_row.get_value())
            msync = self.msync_row.get_active()
            angle = self.angle_row.get_active()
            ripple = self.ripple_row.get_active()

            self.driver.set_dpi_and_sensor(
                stages=stages,
                active_stage=active_stage,
                lod=lod,
                debounce=debounce,
                motion_sync=msync,
                angle_snap=angle,
                ripple=ripple,
            )
            self._show_toast("✓ Paramètres DPI et capteur appliqués !")
        except Exception as e:
            self._show_toast(f"Erreur DPI : {e}")

    def _on_apply_buttons_clicked(self, button=None):
        try:
            btn_map = {}
            for i, combo in enumerate(self.btn_combos):
                action_idx = combo.get_selected()
                act_key = self.btn_action_keys[action_idx]
                btn_map[i + 1] = act_key
            self.driver.set_buttons(btn_map)
            self._show_toast("✓ Mappage des boutons appliqué à la souris !")
        except Exception as e:
            self._show_toast(f"Erreur Boutons : {e}")

    def _on_apply_power_clicked(self, button=None):
        try:
            rate_idx = self.rate_row.get_selected()
            rate_hz = [125, 250, 500, 1000][rate_idx]
            self.driver.set_polling_rate(rate_hz)
            self._show_toast(f"✓ Fréquence de rapport {rate_hz} Hz appliquée !")
        except Exception as e:
            self._show_toast(f"Erreur Taux : {e}")

    def _on_restore_buttons_clicked(self, widget):
        try:
            self.driver.restore_factory_buttons()
            default_keys = ["left_click", "right_click", "middle_click", "forward", "backward"]
            for i, combo in enumerate(self.btn_combos):
                def_key = default_keys[i]
                if def_key in self.btn_action_keys:
                    combo.set_selected(self.btn_action_keys.index(def_key))
            self._show_toast("✓ Mappage des boutons d'usine restauré !")
        except Exception as e:
            self._show_toast(f"Erreur : {e}")

    def _show_toast(self, message: str):
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self.add_toast(toast)

    def _on_stage_radio_toggled(self, radio, stage_num):
        if getattr(self, "_updating_ui", False):
            return
        if radio.get_active():
            try:
                self.driver.set_dpi_and_sensor(active_stage=stage_num)
                stages = self.driver.config.get("dpi_stages", [400, 800, 1600, 3200, 6400, 26000])
                dpi_val = stages[stage_num - 1] if 1 <= stage_num <= len(stages) else ""
                self._show_toast(f"✓ Étape {stage_num} activée ({dpi_val} DPI)")
            except Exception as e:
                self._show_toast(f"Erreur : {e}")

    def _periodic_refresh(self):
        st = self.driver.query_status(poll_hardware=False)
        bat = st["battery"]
        charging = st["charging"]
        ch_str = " (En charge ⚡)" if charging else ""
        self.battery_row.set_subtitle(f"{bat}%{ch_str}")
        self.bat_progress.set_fraction(max(0.0, min(1.0, bat / 100.0)))

        # Synchronize active DPI stage if changed via physical mouse button
        active_stage = st.get("active_stage", 2)
        if hasattr(self, "stage_radios") and 1 <= active_stage <= len(self.stage_radios):
            radio = self.stage_radios[active_stage - 1]
            if not radio.get_active():
                self._updating_ui = True
                try:
                    radio.set_active(True)
                finally:
                    self._updating_ui = False
        return True


class SkillkorpApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.skillkorp.m20")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SkillkorpM20Window(self)
        win.present()


def main():
    app = SkillkorpApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
