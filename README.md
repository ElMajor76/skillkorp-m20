# Pilote & Gestionnaire Linux pour SkillKorp M20 Ultimate

Ce projet est une réimplémentation native sous Linux du logiciel Windows officiel pour la souris gaming sans fil **SkillKorp M20 Ultimate** (`SourisM20Ultimate.exe`).

---

## 🔍 Analyse & Rétro-ingénierie du Protocole

L'analyse binaire (`MU_SkillKorp.exe` et `hiddriver_1.dll`) a permis de découvrir :
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
   Profil, étape active, masque des étapes activées, valeurs DPI (divisées par 50, octets de poids faible et fort), LOD (1 mm ou 2 mm), Debounce (0-20 ms), Motion Sync, Angle Snapping, Ripple Control et couleurs RVB par étape.
3. **Éclairage RVB (Report ID `0x05` - 15 octets)** :
   12 modes d'éclairage (Éteint, Fixe, Respiration, Néon, Onde, etc.), luminosité (1-8), vitesse (1-8), composantes R, V, B et somme de contrôle sur 16 bits.
4. **Attribution des Boutons (Report ID `0x08` - 59 octets)** :
   Configuration des 6 boutons physiques (clic gauche, clic droit, molette, avant, arrière, cycle DPI, multimédia, etc.).
5. **Requête d'état & Batterie (Report ID `0x0C` & `0x03`)** :
   Envoi de la requête `0x0C`, réception de la trame `0x03 0x10 0x40 [statut_charge] [pourcentage_batterie]`.

---

## 🛠️ Outils Disponibles

### 1. Utilitaire en Ligne de Commande : `m20ctl`

Disponible directement dans le terminal :

```bash
# Vérifier l'état de la souris et de la batterie
m20ctl status

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

# Écouter en direct les événements de changement de DPI et niveau de batterie
m20ctl monitor
```

### 2. Application Graphique Moderne : `m20-gui`

Une interface graphique moderne conçue avec **GTK 4** et **Libadwaita** (style GNOME natif) :
- Accessible depuis la liste des applications GNOME sous le nom **SkillKorp M20 Ultimate**
- Ou en ligne de commande :
```bash
m20-gui
```

---

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
# Générer ou télécharger le paquet RPM
sudo dnf install dist/skillkorp-m20-*.rpm
```

### Option C : Paquet DEB (Debian, Ubuntu, Linux Mint, Pop!_OS)
```bash
# Générer ou télécharger le paquet DEB
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

