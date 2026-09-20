#!/usr/bin/env python3
"""
Packaging Script for SkillKorp M20 Ultimate
Builds RPM (.rpm), DEB (.deb), and Arch packages.
"""

import os
import sys
import shutil
import subprocess
import tarfile
import hashlib
import time

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(os.path.realpath(__file__))))
DIST_DIR = os.path.join(REPO_DIR, "dist")
VERSION = "1.2.2"
RELEASE = "1"
PKG_NAME = "skillkorp-m20"


def clean():
    os.makedirs(DIST_DIR, exist_ok=True)
    for f in os.listdir(DIST_DIR):
        p = os.path.join(DIST_DIR, f)
        if os.path.isfile(p):
            os.remove(p)


def build_rpm():
    print("\n📦 [1/3] Construction du paquet RPM (Fedora / RHEL / openSUSE)...")
    if not shutil.which("rpmbuild"):
        print("  ⚠️ rpmbuild n'est pas disponible, génération RPM ignorée.")
        return None

    rpm_root = os.path.join(REPO_DIR, "build_rpm")
    shutil.rmtree(rpm_root, ignore_errors=True)
    for sub in ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"]:
        os.makedirs(os.path.join(rpm_root, sub), exist_ok=True)

    spec_src = os.path.join(REPO_DIR, "packaging", "rpm", f"{PKG_NAME}.spec")
    spec_dst = os.path.join(rpm_root, "SPECS", f"{PKG_NAME}.spec")
    shutil.copy2(spec_src, spec_dst)

    cmd = [
        "rpmbuild",
        "-bb",
        f"--define=_topdir {rpm_root}",
        f"--define=_sourcedir {REPO_DIR}",
        spec_dst,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ❌ Erreur rpmbuild: {res.stderr}")
        return None

    rpm_file = None
    for root, _, files in os.walk(os.path.join(rpm_root, "RPMS")):
        for f in files:
            if f.endswith(".rpm"):
                src_path = os.path.join(root, f)
                dst_path = os.path.join(DIST_DIR, f)
                shutil.copy2(src_path, dst_path)
                rpm_file = dst_path
                print(f"  ✓ Paquet RPM généré : {dst_path}")

    shutil.rmtree(rpm_root, ignore_errors=True)
    return rpm_file


def build_deb():
    print("\n📦 [2/3] Construction du paquet DEB (Debian / Ubuntu / Linux Mint)...")
    deb_root = os.path.join(REPO_DIR, "build_deb")
    shutil.rmtree(deb_root, ignore_errors=True)

    # File structure
    share_dir = os.path.join(deb_root, "usr", "share", PKG_NAME)
    bin_dir = os.path.join(deb_root, "usr", "bin")
    udev_dir = os.path.join(deb_root, "usr", "lib", "udev", "rules.d")
    app_dir = os.path.join(deb_root, "usr", "share", "applications")
    icon_dir = os.path.join(deb_root, "usr", "share", "icons", "hicolor", "256x256", "apps")
    doc_dir = os.path.join(deb_root, "usr", "share", "doc", PKG_NAME)
    debian_dir = os.path.join(deb_root, "DEBIAN")

    for d in [share_dir, bin_dir, udev_dir, app_dir, icon_dir, doc_dir, debian_dir]:
        os.makedirs(d, exist_ok=True)

    # Copy files
    shutil.copy2(os.path.join(REPO_DIR, "m20_driver.py"), os.path.join(share_dir, "m20_driver.py"))
    shutil.copy2(os.path.join(REPO_DIR, "profile_manager.py"), os.path.join(share_dir, "profile_manager.py"))
    shutil.copy2(os.path.join(REPO_DIR, "m20_gui.py"), os.path.join(share_dir, "m20_gui.py"))
    shutil.copy2(os.path.join(REPO_DIR, "m20_tray.py"), os.path.join(share_dir, "m20_tray.py"))
    shutil.copy2(os.path.join(REPO_DIR, "m20ctl"), os.path.join(share_dir, "m20ctl"))
    shutil.copytree(os.path.join(REPO_DIR, "assets"), os.path.join(share_dir, "assets"), dirs_exist_ok=True)

    os.chmod(os.path.join(share_dir, "m20_driver.py"), 0o755)
    os.chmod(os.path.join(share_dir, "profile_manager.py"), 0o755)
    os.chmod(os.path.join(share_dir, "m20_gui.py"), 0o755)
    os.chmod(os.path.join(share_dir, "m20_tray.py"), 0o755)
    os.chmod(os.path.join(share_dir, "m20ctl"), 0o755)

    # Symlinks
    os.symlink(f"/usr/share/{PKG_NAME}/m20ctl", os.path.join(bin_dir, "m20ctl"))
    os.symlink(f"/usr/share/{PKG_NAME}/m20_gui.py", os.path.join(bin_dir, "m20-gui"))
    os.symlink(f"/usr/share/{PKG_NAME}/m20_tray.py", os.path.join(bin_dir, "m20-tray"))

    # Udev, desktop, icon, docs
    shutil.copy2(os.path.join(REPO_DIR, "udev", "99-skillkorp-m20.rules"), os.path.join(udev_dir, "99-skillkorp-m20.rules"))
    shutil.copy2(os.path.join(REPO_DIR, "io.github.skillkorp.m20.desktop"), os.path.join(app_dir, "io.github.skillkorp.m20.desktop"))
    shutil.copy2(os.path.join(REPO_DIR, "assets", "skillkorp-m20.png"), os.path.join(icon_dir, "skillkorp-m20.png"))
    shutil.copy2(os.path.join(REPO_DIR, "LICENSE"), os.path.join(doc_dir, "copyright"))
    shutil.copy2(os.path.join(REPO_DIR, "README.md"), os.path.join(doc_dir, "README.md"))

    # Control scripts
    shutil.copy2(os.path.join(REPO_DIR, "packaging", "deb", "control"), os.path.join(debian_dir, "control"))
    shutil.copy2(os.path.join(REPO_DIR, "packaging", "deb", "postinst"), os.path.join(debian_dir, "postinst"))
    shutil.copy2(os.path.join(REPO_DIR, "packaging", "deb", "postrm"), os.path.join(debian_dir, "postrm"))
    os.chmod(os.path.join(debian_dir, "postinst"), 0o755)
    os.chmod(os.path.join(debian_dir, "postrm"), 0o755)

    # Calculate md5sums
    md5_lines = []
    for root, _, files in os.walk(os.path.join(deb_root, "usr")):
        for f in files:
            full_path = os.path.join(root, f)
            if not os.path.islink(full_path):
                rel_path = os.path.relpath(full_path, deb_root)
                with open(full_path, "rb") as fp:
                    digest = hashlib.md5(fp.read()).hexdigest()
                md5_lines.append(f"{digest}  {rel_path}\n")
    with open(os.path.join(debian_dir, "md5sums"), "w") as fp:
        fp.writelines(sorted(md5_lines))

    deb_filename = f"{PKG_NAME}_{VERSION}_{'all'}.deb"
    deb_dst = os.path.join(DIST_DIR, deb_filename)

    # Check if dpkg-deb is available
    if shutil.which("dpkg-deb"):
        res = subprocess.run(["dpkg-deb", "--build", "--root-owner-group", deb_root, deb_dst], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  ✓ Paquet DEB généré (via dpkg-deb) : {deb_dst}")
            shutil.rmtree(deb_root, ignore_errors=True)
            return deb_dst

    # Pure Python / ar fallback
    ar_cmd = shutil.which("ar")
    if not ar_cmd:
        print("  ❌ 'ar' n'est pas disponible pour assembler le paquet .deb.")
        return None

    # Pack control.tar.gz
    ctrl_tar = os.path.join(deb_root, "control.tar.gz")
    with tarfile.open(ctrl_tar, "w:gz") as tar:
        for f in sorted(os.listdir(debian_dir)):
            fp = os.path.join(debian_dir, f)
            ti = tar.gettarinfo(fp, arcname=f"./{f}")
            ti.uid = 0
            ti.gid = 0
            ti.uname = "root"
            ti.gname = "root"
            if f in ("postinst", "postrm"):
                ti.mode = 0o755
            else:
                ti.mode = 0o644
            if os.path.isfile(fp):
                with open(fp, "rb") as content_file:
                    tar.addfile(ti, content_file)

    # Pack data.tar.gz
    data_tar = os.path.join(deb_root, "data.tar.gz")
    with tarfile.open(data_tar, "w:gz") as tar:
        usr_dir = os.path.join(deb_root, "usr")
        for root, dirs, files in os.walk(usr_dir):
            rel_dir = os.path.relpath(root, deb_root)
            d_ti = tar.gettarinfo(root, arcname=f"./{rel_dir}")
            d_ti.uid = 0
            d_ti.gid = 0
            d_ti.uname = "root"
            d_ti.gname = "root"
            d_ti.mode = 0o755
            tar.addfile(d_ti)
            for f in files:
                fp = os.path.join(root, f)
                rel_file = os.path.relpath(fp, deb_root)
                f_ti = tar.gettarinfo(fp, arcname=f"./{rel_file}")
                f_ti.uid = 0
                f_ti.gid = 0
                f_ti.uname = "root"
                f_ti.gname = "root"
                if os.path.islink(fp):
                    tar.addfile(f_ti)
                else:
                    if "bin" in rel_file or f.endswith(".py") or f == "m20ctl":
                        f_ti.mode = 0o755
                    else:
                        f_ti.mode = 0o644
                    with open(fp, "rb") as content_file:
                        tar.addfile(f_ti, content_file)

    # Write debian-binary
    deb_bin = os.path.join(deb_root, "debian-binary")
    with open(deb_bin, "w") as fp:
        fp.write("2.0\n")

    # Assemble using ar
    cmd = [ar_cmd, "rc", deb_dst, deb_bin, ctrl_tar, data_tar]
    res = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(deb_root, ignore_errors=True)

    if res.returncode == 0:
        print(f"  ✓ Paquet DEB généré (via standard ar/tar) : {deb_dst}")
        return deb_dst
    else:
        print(f"  ❌ Erreur ar: {res.stderr}")
        return None


def build_source_tarball():
    print("\n📦 [3/3] Création de l'archive source (tarball universel & Arch Linux)...")
    tar_name = f"{PKG_NAME}-{VERSION}.tar.gz"
    tar_path = os.path.join(DIST_DIR, tar_name)
    with tarfile.open(tar_path, "w:gz") as tar:
        for f in [
            "m20_driver.py",
            "profile_manager.py",
            "m20_gui.py",
            "m20_tray.py",
            "m20ctl",
            "install.sh",
            "LICENSE",
            "README.md",
            "CHANGELOG.md",
            "io.github.skillkorp.m20.desktop",
        ]:
            fp = os.path.join(REPO_DIR, f)
            if os.path.exists(fp):
                tar.add(fp, arcname=f"{PKG_NAME}-{VERSION}/{f}")
        for folder in ["udev", "assets", "packaging"]:
            folder_path = os.path.join(REPO_DIR, folder)
            if os.path.exists(folder_path):
                tar.add(folder_path, arcname=f"{PKG_NAME}-{VERSION}/{folder}")

    print(f"  ✓ Archive source générée : {tar_path}")
    return tar_path


def main():
    print("=" * 60)
    print("  Génération des paquets SkillKorp M20 Ultimate")
    print(f"  Version : {VERSION}-{RELEASE}")
    print("=" * 60)

    clean()
    rpm = build_rpm()
    deb = build_deb()
    tar = build_source_tarball()

    print("\n" + "=" * 60)
    print("  RÉSUMÉ DES PAQUETS GÉNÉRÉS DANS dist/ :")
    for f in os.listdir(DIST_DIR):
        size = os.path.getsize(os.path.join(DIST_DIR, f))
        print(f"  • {f} ({size / 1024:.1f} KiB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
