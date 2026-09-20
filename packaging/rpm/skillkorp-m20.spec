%{!?_udevrulesdir: %global _udevrulesdir %{_prefix}/lib/udev/rules.d}

Name:           skillkorp-m20
Version:        1.0.0
Release:        1%{?dist}
Summary:        Pilote et interface graphique Linux pour souris SkillKorp M20 Ultimate
License:        MIT
URL:            https://github.com/ElMajor76/skillkorp-m20
BuildArch:      noarch

Requires:       python3
Requires:       python3-gobject
Requires:       libadwaita
Requires:       systemd-udev

%description
Pilote natif sous Linux, outil CLI (m20ctl) et application GTK 4 / Libadwaita
(m20-gui) pour la souris sans fil de jeu SkillKorp M20 Ultimate (capteur PixArt
PAW3395 et microcontrôleur Beken BK3633).

%prep
# Pas d'étape de compilation requise

%build
# Scripts Python, rien à compiler

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}%{_datadir}/skillkorp-m20
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_udevrulesdir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps

# Fichiers de l'application
install -m 0755 %{_sourcedir}/m20_driver.py %{buildroot}%{_datadir}/skillkorp-m20/m20_driver.py
install -m 0755 %{_sourcedir}/m20_gui.py %{buildroot}%{_datadir}/skillkorp-m20/m20_gui.py
install -m 0755 %{_sourcedir}/m20ctl %{buildroot}%{_datadir}/skillkorp-m20/m20ctl

# Liens symboliques dans /usr/bin
ln -s %{_datadir}/skillkorp-m20/m20ctl %{buildroot}%{_bindir}/m20ctl
ln -s %{_datadir}/skillkorp-m20/m20_gui.py %{buildroot}%{_bindir}/m20-gui

# Règle udev, lanceur .desktop et icône
install -m 0644 %{_sourcedir}/udev/99-skillkorp-m20.rules %{buildroot}%{_udevrulesdir}/99-skillkorp-m20.rules
install -m 0644 %{_sourcedir}/io.github.skillkorp.m20.desktop %{buildroot}%{_datadir}/applications/io.github.skillkorp.m20.desktop
install -m 0644 %{_sourcedir}/assets/skillkorp-m20.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/skillkorp-m20.png

%post
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=hidraw >/dev/null 2>&1 || :
update-desktop-database %{_datadir}/applications >/dev/null 2>&1 || :

%postun
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=hidraw >/dev/null 2>&1 || :
update-desktop-database %{_datadir}/applications >/dev/null 2>&1 || :

%files
%{_datadir}/skillkorp-m20
%{_bindir}/m20ctl
%{_bindir}/m20-gui
%{_udevrulesdir}/99-skillkorp-m20.rules
%{_datadir}/applications/io.github.skillkorp.m20.desktop
%{_datadir}/icons/hicolor/256x256/apps/skillkorp-m20.png

%changelog
* Sun Sep 20 2026 nplacide <nplacide95@gmail.com> - 1.0.0-1
- Version initiale avec support sans fil 2.4 GHz et filaire USB-C
