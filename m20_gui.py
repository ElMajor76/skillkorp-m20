#!/usr/bin/env python3
"""
SkillKorp M20 Ultimate - Application Graphique Linux (GTK 4 / Libadwaita)
Fonctionnalités :
- Gestion multi-profils (Défaut, Gaming FPS, Bureautique, Profils personnalisés)
- Bascule automatique des profils selon l'application active
- Sensibilité DPI (50 à 26 000 DPI) et paramètres capteur PixArt PAW3395
- Attribution visuelle et interactive des 5 boutons avec schéma vectoriel de la souris
- Gestion de l'alimentation, délai de veille matérielle (1-60 min) et mode de réveil
- Intégration de l'indicateur dans la barre des tâches et autostart
"""

import sys
import os
import time
import subprocess
from typing import Optional, Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from m20_driver import SkillkorpM20Driver, BUTTON_ACTIONS, POLLING_RATE_MAP
from profile_manager import (
    ProfileManager,
    detect_active_window_class,
    is_autostart_enabled,
    set_autostart,
)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Gdk


class SkillkorpM20Window(Adw.PreferencesWindow):
    def __init__(self, app):
        super().__init__(application=app, title="SkillKorp M20 Ultimate")
        self.set_default_size(840, 720)

        self.driver = SkillkorpM20Driver()
        self.pm = ProfileManager()
        self._updating_ui = False

        # Custom CSS for interactive mouse schematic overlay buttons
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string("""
        .mouse-overlay-btn {
            background-color: transparent;
            border-radius: 8px;
            border: 1px solid transparent;
            transition: all 150ms ease-in-out;
        }
        .mouse-overlay-btn:hover {
            background-color: rgba(53, 132, 228, 0.35);
            border: 1px solid rgba(53, 132, 228, 0.7);
        }
        .mouse-overlay-btn:active {
            background-color: rgba(53, 132, 228, 0.6);
        }
        """)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        # Load active profile data
        self.current_profile_id = self.pm.get_active_profile_id()

        # Build UI pages
        self._init_profiles_page()
        self._init_dpi_page()
        self._init_buttons_page()
        self._init_power_page()

        # Sync UI fields with active profile / driver
        self._sync_ui_from_current_profile()

        # Periodic status refresh (battery, hardware DPI sync)
        GLib.timeout_add_seconds(1, self._periodic_refresh)

    # -------------------------------------------------------------------------
    # 1. PROFILES PAGE
    # -------------------------------------------------------------------------
    def _init_profiles_page(self):
        page = Adw.PreferencesPage(title="Profils", icon_name="document-properties-symbolic")
        self.add(page)

        # Active Profile Selection Group
        prof_group = Adw.PreferencesGroup(
            title="Profil de Configuration Actif",
            description="Choisissez ou personnalisez les profils de configuration de la souris",
        )
        page.add(prof_group)

        self.profile_combo = Adw.ComboRow(title="Profil actuel")
        self._refresh_profile_combo()
        self.profile_combo.connect("notify::selected", self._on_profile_combo_changed)
        prof_group.add(self.profile_combo)

        # Profile Actions Box
        actions_group = Adw.PreferencesGroup(title="Gestion des Profils")
        page.add(actions_group)

        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_box.set_halign(Gtk.Align.CENTER)

        new_btn = Gtk.Button(label="Nouveau profil...")
        new_btn.add_css_class("suggested-action")
        new_btn.connect("clicked", self._on_new_profile_clicked)
        action_box.append(new_btn)

        self.del_btn = Gtk.Button(label="Supprimer le profil")
        self.del_btn.add_css_class("destructive-action")
        self.del_btn.connect("clicked", self._on_delete_profile_clicked)
        action_box.append(self.del_btn)

        export_btn = Gtk.Button(label="Exporter...")
        export_btn.connect("clicked", self._on_export_profile_clicked)
        action_box.append(export_btn)

        import_btn = Gtk.Button(label="Importer...")
        import_btn.connect("clicked", self._on_import_profile_clicked)
        action_box.append(import_btn)

        actions_group.add(action_box)

        # Auto-switch Group
        auto_group = Adw.PreferencesGroup(
            title="Bascule Automatique par Jeu / Application",
            description="Permet à la souris d'adapter ses réglages automatiquement selon l'application active",
        )
        page.add(auto_group)

        self.auto_switch_row = Adw.SwitchRow(
            title="Activer la bascule automatique",
            subtitle="Détecte le lancement de vos jeux (CS2, Valorant...) ou logiciels de bureautique",
        )
        self.auto_switch_row.set_active(self.pm.is_auto_switch_enabled())
        self.auto_switch_row.connect("notify::active", self._on_auto_switch_toggled)
        auto_group.add(self.auto_switch_row)

    def _refresh_profile_combo(self):
        profiles = self.pm.list_profiles()
        self.profile_ids = [p["id"] for p in profiles]
        labels = [f"{p.get('name', p['id'])} ({p.get('description', '')})" for p in profiles]
        string_list = Gtk.StringList.new(labels)
        self.profile_combo.set_model(string_list)

        cur_id = self.pm.get_active_profile_id()
        if cur_id in self.profile_ids:
            self.profile_combo.set_selected(self.profile_ids.index(cur_id))

    def _on_profile_combo_changed(self, row, param):
        if self._updating_ui:
            return
        idx = row.get_selected()
        if 0 <= idx < len(self.profile_ids):
            target_id = self.profile_ids[idx]
            if target_id != self.current_profile_id:
                try:
                    prof = self.pm.switch_profile(target_id, driver=self.driver)
                    self.current_profile_id = target_id
                    self._sync_ui_from_current_profile()
                    self._show_toast(f"✓ Profil '{prof.get('name', target_id)}' activé et appliqué !")
                except Exception as e:
                    self._show_toast(f"Erreur : {e}")

    def _on_new_profile_clicked(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Créer un nouveau profil",
            body="Entrez le nom de votre nouveau profil de souris :",
        )
        entry = Gtk.Entry()
        entry.set_placeholder_text("Ex : Apex Legends, Montage Vidéo...")
        entry.set_margin_start(24)
        entry.set_margin_end(24)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Annuler")
        dialog.add_response("create", "Créer")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dlg, response):
            if response == "create":
                text = entry.get_text().strip()
                if text:
                    safe_id = text.lower().replace(" ", "_")
                    try:
                        self.pm.create_profile(safe_id, name=text, copy_from=self.current_profile_id)
                        self.pm.switch_profile(safe_id, driver=self.driver)
                        self.current_profile_id = safe_id
                        self._refresh_profile_combo()
                        self._sync_ui_from_current_profile()
                        self._show_toast(f"✓ Profil '{text}' créé avec succès !")
                    except Exception as e:
                        self._show_toast(f"Erreur : {e}")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_delete_profile_clicked(self, button):
        if self.current_profile_id == "default":
            self._show_toast("Le profil par défaut ne peut pas être supprimé.")
            return

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Supprimer le profil",
            body=f"Voulez-vous vraiment supprimer définitivement le profil '{self.current_profile_id}' ?",
        )
        dialog.add_response("cancel", "Annuler")
        dialog.add_response("delete", "Supprimer")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(dlg, response):
            if response == "delete":
                try:
                    self.pm.delete_profile(self.current_profile_id)
                    self.current_profile_id = "default"
                    self._refresh_profile_combo()
                    self._sync_ui_from_current_profile()
                    self._show_toast("✓ Profil supprimé.")
                except Exception as e:
                    self._show_toast(f"Erreur : {e}")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_export_profile_clicked(self, button):
        export_path = os.path.expanduser(f"~/{self.current_profile_id}.json")
        try:
            self.pm.export_profile(self.current_profile_id, export_path)
            self._show_toast(f"✓ Profil exporté dans : {export_path}")
        except Exception as e:
            self._show_toast(f"Erreur d'export : {e}")

    def _on_import_profile_clicked(self, button):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Importer un profil JSON",
            body="Indiquez le chemin absolu du fichier JSON à importer :",
        )
        entry = Gtk.Entry()
        entry.set_placeholder_text(os.path.expanduser("~/mon_profil.json"))
        entry.set_margin_start(24)
        entry.set_margin_end(24)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Annuler")
        dialog.add_response("import", "Importer")
        dialog.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dlg, response):
            if response == "import":
                path = entry.get_text().strip()
                if path and os.path.exists(path):
                    try:
                        new_id = self.pm.import_profile(path)
                        self.pm.switch_profile(new_id, driver=self.driver)
                        self.current_profile_id = new_id
                        self._refresh_profile_combo()
                        self._sync_ui_from_current_profile()
                        self._show_toast(f"✓ Profil '{new_id}' importé avec succès !")
                    except Exception as e:
                        self._show_toast(f"Erreur d'import : {e}")
                else:
                    self._show_toast("Fichier introuvable.")

        dialog.connect("response", on_response)
        dialog.present()

    def _on_auto_switch_toggled(self, row, param):
        self.pm.set_auto_switch_enabled(row.get_active())

    # -------------------------------------------------------------------------
    # 2. DPI & SENSOR PAGE
    # -------------------------------------------------------------------------
    def _init_dpi_page(self):
        page = Adw.PreferencesPage(title="DPI et Capteur", icon_name="input-mouse-symbolic")
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
        self.debounce_row = Adw.SpinRow(title="Temps de réponse touches (Debounce)", subtitle="Anti-rebond matériel des switchs", adjustment=deb_adj)
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

    # -------------------------------------------------------------------------
    # 3. BUTTONS PAGE (WITH VECTOR MOUSE SCHEMATIC)
    # -------------------------------------------------------------------------
    def _init_buttons_page(self):
        page = Adw.PreferencesPage(title="Boutons", icon_name="input-gaming-symbolic")
        self.add(page)

        # Main Layout: Schematic and Configuration
        main_group = Adw.PreferencesGroup(
            title="Attribution Visuelle des Boutons",
            description="Cliquez sur un bouton du schéma ou sélectionnez une action dans la liste",
        )
        page.add(main_group)

        # Container box
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        hbox.set_margin_top(12)
        hbox.set_margin_bottom(12)
        hbox.set_halign(Gtk.Align.CENTER)

        # Configuration and labels
        self.btn_action_keys = list(BUTTON_ACTIONS.keys())
        btn_action_labels = [info[0] for info in BUTTON_ACTIONS.values()]
        button_names = [
            "1. Clic Gauche (Principal)",
            "2. Clic Droit (Secondaire)",
            "3. Molette (Clic Central)",
            "4. Latéral Avant (Suivant)",
            "5. Latéral Arrière (Précédent)",
            "6. DPI Cycle (Sous la souris)",
        ]
        default_actions = ["left_click", "right_click", "middle_click", "forward", "backward", "dpi_cycle"]
        current_buttons = self.driver.config.get("buttons", {})

        # Left: Interactive Mouse Schematic Card with Faithful Visual
        schematic_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        schematic_card.add_css_class("card")
        schematic_card.set_margin_top(4)
        schematic_card.set_margin_bottom(4)
        schematic_card.set_margin_start(4)
        schematic_card.set_margin_end(4)
        schematic_card.set_size_request(240, 420)
        schematic_card.set_halign(Gtk.Align.CENTER)

        overlay = Gtk.Overlay()
        overlay.set_size_request(194, 360)
        overlay.set_halign(Gtk.Align.CENTER)
        overlay.set_margin_top(8)

        img_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "mouse_view.png")
        if not os.path.exists(img_path):
            img_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "mouse_clean.png")
        if not os.path.exists(img_path):
            img_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets", "m20_schematic.svg")

        if os.path.exists(img_path):
            picture = Gtk.Picture.new_for_filename(img_path)
            picture.set_can_shrink(False)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_size_request(194, 360)
            overlay.set_child(picture)

            # 5 interactive overlay zones over the top-view mouse (btn_num, tooltip, x, y, width, height)
            zones = [
                (1, "1. Clic Gauche", 18, 5, 68, 135),
                (2, "2. Clic Droit", 110, 5, 68, 135),
                (3, "3. Molette (Clic Central)", 84, 28, 26, 72),
                (4, "4. Latéral Avant (Suivant)", 0, 110, 26, 50),
                (5, "5. Latéral Arrière (Précédent)", 0, 166, 26, 52),
            ]
            for btn_num, tooltip, x, y, w, h in zones:
                btn_zone = Gtk.Button()
                btn_zone.add_css_class("flat")
                btn_zone.add_css_class("mouse-overlay-btn")
                btn_zone.set_tooltip_text(tooltip)
                btn_zone.set_halign(Gtk.Align.START)
                btn_zone.set_valign(Gtk.Align.START)
                btn_zone.set_margin_start(x)
                btn_zone.set_margin_top(y)
                btn_zone.set_size_request(w, h)
                btn_zone.connect("clicked", self._on_schematic_btn_clicked, btn_num)
                overlay.add_overlay(btn_zone)

        schematic_card.append(overlay)

        # Quick Jump Button Pills under schematic
        pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pill_box.set_halign(Gtk.Align.CENTER)
        pill_box.set_margin_top(4)
        pill_box.set_margin_bottom(8)

        for btn_num in range(1, 6):
            btn_pill = Gtk.Button(label=f"[{btn_num}]")
            btn_pill.add_css_class("circular")
            btn_pill.set_tooltip_text(button_names[btn_num - 1])
            btn_pill.connect("clicked", self._on_schematic_btn_clicked, btn_num)
            pill_box.append(btn_pill)

        # Button 6 pill: clearly indicated as located under the mouse
        btn6_pill = Gtk.Button(label="[6] DPI (dessous)")
        btn6_pill.add_css_class("pill")
        btn6_pill.set_tooltip_text("6. DPI Cycle — Bouton situé sous la souris")
        btn6_pill.connect("clicked", self._on_schematic_btn_clicked, 6)
        pill_box.append(btn6_pill)

        schematic_card.append(pill_box)
        hbox.append(schematic_card)

        # Right: The 6 Buttons ComboRows
        btn_rows_box = Gtk.ListBox()
        btn_rows_box.add_css_class("boxed-list")
        btn_rows_box.set_selection_mode(Gtk.SelectionMode.NONE)
        btn_rows_box.set_hexpand(True)
        btn_rows_box.set_valign(Gtk.Align.CENTER)

        self.btn_combos = []
        for i in range(1, 7):
            row = Adw.ComboRow(title=button_names[i - 1])
            string_list = Gtk.StringList.new(btn_action_labels)
            row.set_model(string_list)

            cur_act = current_buttons.get(str(i), default_actions[i - 1])
            try:
                selected_idx = self.btn_action_keys.index(cur_act)
            except ValueError:
                selected_idx = 0
            row.set_selected(selected_idx)
            self.btn_combos.append(row)
            btn_rows_box.append(row)

        hbox.append(btn_rows_box)
        main_group.add(hbox)

        # Action Buttons
        apply_group = Adw.PreferencesGroup()
        page.add(apply_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(8)

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

    def _on_schematic_btn_clicked(self, widget, btn_num: int):
        idx = btn_num - 1
        if 0 <= idx < len(self.btn_combos):
            combo = self.btn_combos[idx]
            combo.grab_focus()
            combo.activate()
            self._show_toast(f"Bouton {btn_num} sélectionné")

    # -------------------------------------------------------------------------
    # 4. POWER & SLEEP PAGE
    # -------------------------------------------------------------------------
    def _init_power_page(self):
        page = Adw.PreferencesPage(title="Alimentation et Veille", icon_name="battery-level-100-charged-symbolic")
        self.add(page)

        # Battery Group
        bat_group = Adw.PreferencesGroup(title="Batterie et Autonomie")
        page.add(bat_group)

        self.battery_row = Adw.ActionRow(title="Niveau de batterie", subtitle="100% (Chargée)")
        self.bat_progress = Gtk.ProgressBar()
        self.bat_progress.set_fraction(1.0)
        self.bat_progress.set_valign(Gtk.Align.CENTER)
        self.bat_progress.set_size_request(160, -1)
        self.battery_row.add_suffix(self.bat_progress)
        bat_group.add(self.battery_row)

        # Sleep Timer & Power Saving Group
        sleep_group = Adw.PreferencesGroup(
            title="Gestion Matérielle de la Mise en Veille",
            description="Configure les seuils de mise en veille automatique de la souris pour maximiser la batterie",
        )
        page.add(sleep_group)

        # Sleep timer slider (1 to 60 minutes)
        cur_sleep = self.driver.config.get("sleep_timer_minutes", 5)
        sleep_adj = Gtk.Adjustment(value=cur_sleep, lower=1, upper=60, step_increment=1, page_increment=5)
        self.sleep_row = Adw.SpinRow(
            title="Délai d'inactivité avant mise en veille",
            subtitle="Durée sans mouvement avant passage en mode veille profonde (1 à 60 minutes)",
            adjustment=sleep_adj,
        )
        sleep_group.add(self.sleep_row)

        # Move to wake switch
        cur_wake = self.driver.config.get("move_to_wake", True)
        self.wake_row = Adw.SwitchRow(
            title="Réveil au mouvement (Move to wake)",
            subtitle="Si désactivé, un clic sur un bouton est requis pour réveiller la souris (idéal en déplacement)",
        )
        self.wake_row.set_active(cur_wake)
        sleep_group.add(self.wake_row)

        # Polling Rate Group
        rate_group = Adw.PreferencesGroup(
            title="Taux de Rapport USB (Polling Rate)",
            description="Fréquence de communication entre la souris et le PC (125 Hz à 1000 Hz)",
        )
        page.add(rate_group)

        self.rate_row = Adw.ComboRow(title="Fréquence de rapport")
        rate_options = [
            "125 Hz (Économie maximale d'énergie - 8 ms)",
            "250 Hz (Bureautique fluide - 4 ms)",
            "500 Hz (Gaming Standard - 2 ms)",
            "1000 Hz (E-Sports Ultra Rapide - 1 ms)",
        ]
        self.rate_row.set_model(Gtk.StringList.new(rate_options))
        cur_rate = self.driver.config.get("polling_rate", 1000)
        rate_idx = 3 if cur_rate == 1000 else 2 if cur_rate == 500 else 1 if cur_rate == 250 else 0
        self.rate_row.set_selected(rate_idx)
        rate_group.add(self.rate_row)

        # System Integration Group (Tray indicator)
        sys_group = Adw.PreferencesGroup(
            title="Intégration au Système Linux",
            description="Indicateur d'état dans la zone de notification (systray)",
        )
        page.add(sys_group)

        self.tray_auto_row = Adw.SwitchRow(
            title="Lancer l'indicateur dans la barre des tâches au démarrage",
            subtitle="Surveille la batterie et permet de changer de DPI / profil en 1 clic",
        )
        self.tray_auto_row.set_active(is_autostart_enabled())
        self.tray_auto_row.connect("notify::active", self._on_tray_autostart_toggled)
        sys_group.add(self.tray_auto_row)

        # Apply button
        apply_group = Adw.PreferencesGroup()
        page.add(apply_group)
        btn = Gtk.Button(label="Enregistrer & Appliquer les Paramètres d'Alimentation")
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", self._on_apply_power_clicked)
        apply_group.add(btn)

    def _on_tray_autostart_toggled(self, row, param):
        set_autostart(row.get_active())
        if row.get_active():
            # If enabled, also launch tray now if not running
            try:
                subprocess.Popen(["m20ctl", "tray", "start"])
            except Exception:
                pass
            self._show_toast("✓ Lancement automatique de l'indicateur activé")
        else:
            self._show_toast("✓ Lancement automatique désactivé")

    # -------------------------------------------------------------------------
    # APPLY HANDLERS & PROFILE PERSISTENCE
    # -------------------------------------------------------------------------
    def _save_to_active_profile(self, updates: Dict[str, Any]):
        prof = self.pm.get_profile(self.current_profile_id)
        if prof:
            prof.update(updates)
            self.pm.save_profile(self.current_profile_id, prof)

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
            self._save_to_active_profile({
                "dpi_stages": stages,
                "active_stage": active_stage,
                "lod": lod,
                "debounce": debounce,
                "motion_sync": msync,
                "angle_snap": angle,
                "ripple": ripple,
            })
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
            self._save_to_active_profile({"buttons": {str(k): v for k, v in btn_map.items()}})
            self._show_toast("✓ Mappage des boutons appliqué à la souris !")
        except Exception as e:
            self._show_toast(f"Erreur Boutons : {e}")

    def _on_apply_power_clicked(self, button=None):
        try:
            rate_idx = self.rate_row.get_selected()
            rate_hz = [125, 250, 500, 1000][rate_idx]
            self.driver.set_polling_rate(rate_hz)

            sleep_min = int(self.sleep_row.get_value())
            move_wake = self.wake_row.get_active()
            self.driver.set_power_settings(sleep_timer_minutes=sleep_min, move_to_wake=move_wake)

            self._save_to_active_profile({
                "polling_rate": rate_hz,
                "sleep_timer_minutes": sleep_min,
                "move_to_wake": move_wake,
            })
            self._show_toast(f"✓ Veille ({sleep_min} min) et taux ({rate_hz} Hz) appliqués !")
        except Exception as e:
            self._show_toast(f"Erreur Alimentation : {e}")

    def _on_restore_buttons_clicked(self, widget):
        try:
            self.driver.restore_factory_buttons()
            default_keys = ["left_click", "right_click", "middle_click", "forward", "backward", "dpi_cycle"]
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
        if self._updating_ui:
            return
        if radio.get_active():
            try:
                self.driver.set_dpi_and_sensor(active_stage=stage_num)
                stages = self.driver.config.get("dpi_stages", [400, 800, 1600, 3200, 6400, 26000])
                dpi_val = stages[stage_num - 1] if 1 <= stage_num <= len(stages) else ""
                self._show_toast(f"✓ Étape {stage_num} activée ({dpi_val} DPI)")
            except Exception as e:
                self._show_toast(f"Erreur : {e}")

    # -------------------------------------------------------------------------
    # UI SYNCHRONIZATION
    # -------------------------------------------------------------------------
    def _sync_ui_from_current_profile(self):
        prof = self.pm.get_profile(self.current_profile_id)
        if not prof:
            return

        self._updating_ui = True
        try:
            # 1. DPI
            stages = prof.get("dpi_stages", [400, 800, 1600, 3200, 6400, 26000])
            for i, spin in enumerate(self.stage_spinners):
                if i < len(stages):
                    spin.set_value(stages[i])
            active_stage = prof.get("active_stage", 2)
            if 1 <= active_stage <= len(self.stage_radios):
                self.stage_radios[active_stage - 1].set_active(True)

            # 2. Sensor
            lod = prof.get("lod", 1)
            self.lod_row.set_selected(0 if lod <= 1 else 1)
            self.debounce_row.set_value(prof.get("debounce", 4))
            self.msync_row.set_active(prof.get("motion_sync", True))
            self.angle_row.set_active(prof.get("angle_snap", False))
            self.ripple_row.set_active(prof.get("ripple", False))

            # 3. Buttons
            buttons = prof.get("buttons", {})
            default_actions = ["left_click", "right_click", "middle_click", "forward", "backward", "dpi_cycle"]
            for i, combo in enumerate(self.btn_combos):
                act = buttons.get(str(i + 1), default_actions[i])
                if act in self.btn_action_keys:
                    combo.set_selected(self.btn_action_keys.index(act))

            # 4. Power & Sleep
            polling = prof.get("polling_rate", 1000)
            rate_idx = 3 if polling == 1000 else 2 if polling == 500 else 1 if polling == 250 else 0
            self.rate_row.set_selected(rate_idx)
            self.sleep_row.set_value(prof.get("sleep_timer_minutes", 5))
            self.wake_row.set_active(prof.get("move_to_wake", True))

            # Enable/disable delete button
            self.del_btn.set_sensitive(self.current_profile_id != "default")

        finally:
            self._updating_ui = False

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
