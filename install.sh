#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installation du pilote & utilitaires SkillKorp M20 Ultimate ==="

# 1. Copie des règles udev
echo "[1/4] Installation des règles udev..."
if [ "$EUID" -eq 0 ]; then
    cp "$SCRIPT_DIR/udev/99-skillkorp-m20.rules" /etc/udev/rules.d/
    udevadm control --reload-rules
    udevadm trigger
else
    echo "Mot de passe requis pour installer la règle udev dans /etc/udev/rules.d/ :"
    sudo cp "$SCRIPT_DIR/udev/99-skillkorp-m20.rules" /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

# 2. Liens symboliques CLI / GUI dans ~/.local/bin
echo "[2/4] Création des exécutables dans ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/m20ctl" "$HOME/.local/bin/m20ctl"
ln -sf "$SCRIPT_DIR/m20_gui.py" "$HOME/.local/bin/m20-gui"

# 3. Icône
echo "[3/4] Installation de l'icône..."
mkdir -p "$HOME/.local/share/icons/hicolor/256x256/apps"
cp "$SCRIPT_DIR/assets/skillkorp-m20.png" "$HOME/.local/share/icons/hicolor/256x256/apps/skillkorp-m20.png"

# 4. Raccourci d'application .desktop
echo "[4/4] Installation du lanceur d'application..."
mkdir -p "$HOME/.local/share/applications"
cp "$SCRIPT_DIR/io.github.skillkorp.m20.desktop" "$HOME/.local/share/applications/"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "✓ Installation terminée avec succès !"
echo "Vous pouvez maintenant lancer :"
echo "  - m20ctl status (dans le terminal)"
echo "  - m20-gui       (ou depuis vos applications GNOME)"
