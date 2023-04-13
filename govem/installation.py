import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import click
from dataclass_wizard import JSONFileWizard

from . import download, settings


TYPE_DOWNLOAD_AUTO = 0
TYPE_DOWNLOAD_RAW = 1
TYPE_LOCAL_FILECOPY = 2
TYPE_DESCRIPTIONS = {
    TYPE_DOWNLOAD_AUTO: "official mirror",
    TYPE_DOWNLOAD_RAW: "custom download",
    TYPE_LOCAL_FILECOPY: "local file copy",
}

DESKTOPFILE_NAME = "godot-{name}.desktop"
DESKTOPFILE_CONTENT = """[Desktop Entry]
Type=Application
Version=1.0
Name=Godot {name}
Comment=Open-Source game engine (godot-{name})
Path={workdir}
Exec={workdir}/godot
Icon={icon}
Terminal=false
Categories=Development
"""

SHIM_INVALID_VERSION = """#!/usr/bin/env sh

echo "The selected godot version was uninstalled."
echo "Please run 'govem select [NAME]' to choose a godot version."
exit 1
"""


@dataclass
class InstallData(JSONFileWizard):
    """
    Class for storing installation metadata. This will be used when running
    `govem refresh [NAME]` to copy a file again or to re-download the version.
    """

    typ: int  # One of the TYPE_* constants
    source: str  # URL or file-path
    unzip: Optional[bool] = None


class InstallationExistsError(FileExistsError):
    pass


class InstallationMissingError(FileNotFoundError):
    pass


def install_download(name: str, url: str, unzip: bool, force: bool = False):
    """
    Downloads the executable, then proceed with a normal file-based installation
    """
    install_dir = settings.data.resolve_datapath(name)
    if install_dir.exists() and not force:
        raise InstallationExistsError(
            f'Installation with name "{name}" already exists!'
        )
    with TemporaryDirectory(prefix="govem_") as tmp:
        filepath = download.get_executable(url, tmp, unzip)
        data = InstallData(TYPE_DOWNLOAD_AUTO, url, unzip)
        install_file(name, data, filepath, force)


def install_file(name: str, data: InstallData, src_file: Path, force: bool = False):
    """
    Installs a file by copying it to the installation directory and creating
    all the other fancy stuff:
    - self-contained mode
    - metadata
    - symlink binary
    - icon
    - desktop file
    """
    install_dir = settings.data.resolve_datapath(name)
    if install_dir.exists() and not force:
        raise InstallationExistsError(
            f'Installation with name "{name}" already exists!'
        )

    click.echo("Copying executable file to installation directory")
    install_dir.mkdir(parents=True, exist_ok=True)
    target_file = install_dir / settings.data.executable_file
    shutil.copy(src_file, target_file)
    target_file.chmod(0o755)

    click.echo("Writing metadata to installation directory")
    data.to_json_file(install_dir / settings.data.info_file)

    click.echo("Ensuring installation has it's own self contained editor data")
    self_contained = install_dir / "._sc_"
    self_contained.touch(exist_ok=True)

    click.echo("Creating symlink in shim directory")
    bin_path = settings.data.resolve_binpath("godot-" + name)
    if bin_path.exists():
        bin_path.unlink(missing_ok=True)
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.symlink_to(target_file)

    click.echo("Copying svg icon to installation directory")
    icon = Path(__file__).parent / "icon.svg"
    shutil.copy(icon, install_dir / "icon.svg")

    click.echo("Creating and installing .desktop file")
    create_desktopfile(name, install_dir, settings.data.desktopfile_install)


def uninstall(name: str):
    """
    Uninstalls a given version by deleting all associated files
    """
    install_dir = settings.data.resolve_datapath(name)
    if not install_dir.exists():
        raise InstallationMissingError(
            f'Installation with name "{name}" does not exists!'
        )
    click.echo("Removing complete installation directory")
    settings.data.resolve_binpath("godot-" + name).unlink(missing_ok=True)
    click.echo("Removing .desktop file")
    remove_desktopfile(name)
    click.echo("Removing symlink from shim directory")
    shutil.rmtree(install_dir)

    selected_file = settings.data.resolve_datapath(settings.data.selected_file)
    if selected_file.exists():
        with open(selected_file, "r") as f:
            selected = f.read()
    else:
        selected = ""
    if selected == name:
        click.secho("Uninstalled version was selected!", fg="red")
        click.secho(
            "Please run `govem select [NAME]` to select a valid version.", fg="red"
        )
        selection_path = settings.data.resolve_binpath("godot")
        selection_path.unlink(missing_ok=True)
        with open(selection_path, "w") as f:
            f.write(SHIM_INVALID_VERSION)
        selection_path.chmod(0o755)


def select(name: str):
    """
    Creates a symlink from `godot` to this specific version
    """
    install_dir = settings.data.resolve_datapath(name)
    if not install_dir.exists():
        raise InstallationMissingError(
            f'Installation with name "{name}" does not exists!'
        )

    click.echo("Creating symlink in shim directory")
    target_file = install_dir / settings.data.executable_file
    bin_path = settings.data.resolve_binpath("godot")
    if bin_path.exists():
        bin_path.unlink(missing_ok=True)
    bin_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.symlink_to(target_file)

    click.echo("Storing which version is selected")
    with open(settings.data.resolve_datapath(settings.data.selected_file), "w") as f:
        f.write(name)


def create_desktopfile(name: str, workdir: Path, install: bool):
    """
    Creates a desktop file for an installation. Optionally installs the desktop
    file via command line tools.
    """
    icon = workdir / "icon.svg"
    content = DESKTOPFILE_CONTENT.format(name=name, workdir=workdir, icon=icon)
    path = workdir / DESKTOPFILE_NAME.format(name=name)
    with open(path, "w") as f:
        f.write(content)
    path.chmod(0o644)
    if install:
        target = Path.home() / ".local/share/applications"
        subprocess.run(["desktop-file-install", f"--dir={target}", path])
        subprocess.run(["update-desktop-database", target])
        subprocess.run(["xdg-desktop-menu", "forceupdate"])


def remove_desktopfile(name: str):
    """
    Removes a desktopfile and updates the systems menu database
    """
    target = (
        Path.home() / ".local/share/applications" / DESKTOPFILE_NAME.format(name=name)
    )
    target.unlink(missing_ok=True)
    subprocess.run(["xdg-desktop-menu", "forceupdate"])
