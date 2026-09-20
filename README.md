# Pilote & Gestionnaire Linux pour SkillKorp M20 Ultimate

Ce projet est une réimplémentation native sous Linux du logiciel Windows officiel pour la souris gaming sans fil **SkillKorp M20 Ultimate** (`SourisM20Ultimate.exe`).

---

## 🔍 Analyse & Rétro-ingénierie du Protocole

L'analyse binaire approfondie (`MU_SkillKorp.exe` et `hiddriver_1.dll`) a permis de découvrir :
- **Architecture matérielle** : Solution sans fil OEM **XinMaiGao / Beken BK3633** associée au capteur optique haute précision **PixArt PAW3395** (jusqu'à 26 000 DPI).
- **Identifiants USB** :
  - **Mode Sans Fil 2.4 GHz (Dongle USB)** : VID `0x1D57`, PID `0xFA60`
  - **Mode Filaire (USB-C)** : VID `0x1D57`, PID `0xFA61`
- **Interface de communication** :
  - La configuration s'effectue via l'interface HID propriétaire (Usage Page `0x000B`) accessible via `/dev/hidraw*`.
  - Les commandes sont transmises sous forme de **HID Feature Reports** (`HIDIOCSFEATURE`).
  - Les notifications en temps réel (changement de DPI, niveau de batterie, état de charge) sont reçues via des **HID Input Reports** (Report ID `0x03`).

### Rapports HID identifiés :
1. **Taux de scrutation (Report ID `0x06` - 9 octets)** :
   Intervalle en millisecondes (`0x01` = 1000 Hz, `0x02` = 500 Hz, `0x04` = 250 Hz, `0x08` = 125 Hz) suivi du complément à 1 (NOT bit à bit).
2. **DPI & Capteur PAW3395 (Report ID `0x04` - 56 octets)** :
   Profil, étape active, masque des étapes activées, valeurs DPI (divisées par 50, octets de poids faible et fort), LOD (1 mm ou 2 mm), Debounce (0-20 ms), Motion Sync, Angle Snapping, Ripple Control.
3. **Mise en veille & Réveil (Report ID `0x05` - 15 octets)** :
   Délai avant mise en veille matérielle (1 à 60 minutes) et mode de réveil (mouvement vs clic requis) avec somme de contrôle sur 16 bits.
4. **Attribution des Boutons (Report ID `0x08` - 59 octets)** :
   Configuration des 5 boutons physiques et défilement avec table d'actions matérielles (clic gauche, clic droit, molette, avant, arrière, multimédia, raccourcis système).
5. **Requête d'état & Batterie (Report ID `0x0C` & `0x03`)** :
   Envoi de la requête `0x0C`, réception de la trame `0x03 0x10 0x40 [statut_charge] [pourcentage_batterie]`.

---

## 🛠️ Outils Disponibles

### 1. Utilitaire en Ligne de Commande : `m20ctl`

Disponible directement dans le terminal :

```bash
# Vérifier l'état de la souris et de la batterie
m20ctl status

# Gestion des profils de configuration
m20ctl profile list
m20ctl profile switch gaming_fps
m20ctl profile create my_profile --copy-from default
m20ctl profile export gaming_fps ~/gaming.json
m20ctl profile import ~/gaming.json

# Configuration de la mise en veille matérielle
m20ctl power --sleep-timer 10 --wake-mode move

# Changer le taux de scrutation (125, 250, 500 ou 1000 Hz)
m20ctl rate --set 1000

# Régler les étapes DPI et sélectionner l'étape active
m20ctl dpi --stages 400,800,1600,3200,6400,26000 --active 2

# Ajuster les paramètres avancés du capteur PixArt
m20ctl sensor --lod 1 --debounce 4 --motion-sync on --angle-snap off

# Réassigner un bouton
m20ctl button --btn 4 --action forward
m20ctl button --list-actions

# Restaurer le mappage d'usine par défaut des boutons
m20ctl restore-buttons

# Gérer l'indicateur de la barre des tâches (systray)
m20ctl tray start
m20ctl tray status
m20ctl tray stop
m20ctl autostart enable

# Écouter en direct les événements de changement de DPI et niveau de batterie
m20ctl monitor
```

### 2. Application Graphique Moderne : `m20-gui`

Une interface graphique moderne conçue avec **GTK 4** et **Libadwaita** :
- **Gestion Multi-Profils** : Bascule instantanée entre vos profils de jeu, bureautique, etc.
- **Bascule Automatique par Application** : Détecte le jeu ou logiciel lancé et applique le profil adapté.
- **DPI & Capteur** : 6 étapes DPI éditables de 50 à 26 000 DPI, LOD, Debounce anti-rebond, Motion Sync.
- **Schéma Vectoriel Interactif** : Schéma SVG de la souris dans l'onglet Boutons avec sélection visuelle.
- **Alimentation & Veille** : Jauge de batterie, seuils de mise en veille (1 à 60 min) et mode de réveil au mouvement.
- **Intégration Système** : Activation en 1 clic de l'indicateur au démarrage.

Accessible depuis le menu des applications sous **SkillKorp M20 Ultimate** ou en ligne de commande :
```bash
m20-gui
```

### 3. Indicateur de Zone de Notification : `m20-tray`

Un indicateur discret pour la barre des tâches GNOME / KDE / XFCE :
- Jauge de batterie dynamique avec alertes bureau (batterie faible, charge en cours).
- Bascule rapide de DPI et de profil en 1 clic depuis le menu contextuel.
- Surveillance automatique de l'application active.

```bash
m20-tray
```

---

## 🚀 Installation & Paquets

Des paquets natifs et un script d'installation automatique sont disponibles pour les principales distributions :

### Option A : Installation automatique universelle
Le script détecte automatiquement votre distribution et utilise le gestionnaire approprié :

```bash
git clone https://github.com/ElMajor76/skillkorp-m20.git
cd skillkorp-m20
./install.sh
```

### Option B : Paquet RPM (Fedora, RHEL, openSUSE)
```bash
sudo dnf install dist/skillkorp-m20-*.rpm
```

### Option C : Paquet DEB (Debian, Ubuntu, Linux Mint, Pop!_OS)
```bash
sudo apt install ./dist/skillkorp-m20_*_all.deb
```

### Option D : Arch Linux / Manjaro (PKGBUILD)
```bash
cd packaging/arch
makepkg -si
```

### Génération des paquets (`.rpm`, `.deb`, source)
Pour régénérer les paquets depuis les sources :
```bash
./packaging/build_packages.py
```
Les fichiers générés se trouvent dans le répertoire `dist/`.

---

## 🔒 Permissions udev (Sans Root)

Les règles udev fournies dans `udev/99-skillkorp-m20.rules` permettent à votre compte utilisateur de communiquer directement avec la souris (en USB ou sans fil 2.4G) sans nécessiter les droits `sudo`.

---

## 📄 Licence

Ce projet est sous licence **MIT**. Consultez le fichier [LICENSE](LICENSE) pour plus de détails.
