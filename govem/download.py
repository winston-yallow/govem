import io
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Optional
from urllib.parse import urljoin

import click
import requests
from bs4 import BeautifulSoup
from dataclass_wizard import JSONFileWizard


VERSION_REGEX = re.compile(r"\d*\.\d*(\.\d)?")
FLAVOR_REGEX = re.compile(r"\d*")

EXECUTABLE_BITS = 0b001001001


@dataclass
class VersionData:
    """
    Specifies the metadata for a version
    """

    CHANNEL_STABLE: ClassVar[int] = 1
    CHANNEL_RC: ClassVar[int] = 2
    CHANNEL_BETA: ClassVar[int] = 3
    CHANNEL_ALPHA: ClassVar[int] = 4

    name: str
    channel: int
    default: str  # URL to default download
    mono: Optional[str] = None  # optional URL for mono version


@dataclass
class VersionsListData(JSONFileWizard):
    """
    Stores the list of versions.
    Currently it does not store any more information, but it is planned
    to also store the time of the last update. Inherists from JSONFileWizard
    for automagic serialisation.
    """

    versions: list[VersionData] = field(default_factory=list)


class TuxFamilySoup(BeautifulSoup):
    """
    A beautiful helper class that can elegantly iterate directories on tuxfamily.org
    Ideally we could use the SFTP interface to have a filesystem like API, but it
    seems like tuxfamily.org doesn't allow anonymous access. Scraping is the next
    best options, especially since the structure doesn't seem to change often.
    """

    def __init__(self, url):
        result = requests.get(url)
        result.raise_for_status()
        self.base_url = url
        super().__init__(result.text, features="html.parser")

    def get_directories(self, key_filter=lambda x: True) -> dict[str, str]:
        return {
            i.string: urljoin(self.base_url, i["href"])
            for i in self.find_nested("tr", "td", "a")
            if key_filter(i.string)
        }

    def find_nested(self, *args) -> list[BeautifulSoup]:
        return self._find_nested([self], *args)

    def _find_nested(self, items: list[BeautifulSoup], *args) -> list[BeautifulSoup]:
        if not args:
            return items
        results = []
        for i in items:
            results += self._find_nested(i.find_all(args[0]), *args[1:])
        return results


# BE WARNED!
# THE FOLLOWING CODE WAS WRITTEN AS A FIRST PROTOTYPE AND NEVER REFACTORED.
# THERE MAY BE:
#  - NAMING INCONSISTENCIES
#  - LEFTOVER-TODOS
#  - MISSING METHOD DESCRIPTIONS
#  - UNEXPLAINED WEBSCRAPING WEIRDNESS

# TODO: Double check (and probably refactor) code below this line


FLAVOR_MAPPING: dict[str, int] = {
    "stable": VersionData.CHANNEL_STABLE,
    "rc": VersionData.CHANNEL_RC,
    "beta": VersionData.CHANNEL_BETA,
    "alpha": VersionData.CHANNEL_ALPHA,
}


def get_executable(src: str, dest_dir: Path, unzip: bool) -> Path:
    # TODO:
    #  - download in chunks so that we can show a progressbar
    #  - split into two methods for zip and file downloads
    #  - handle mono downloads correctly (probably needs changes to installation too)
    click.echo(f"Downloading from {src}")
    result = requests.get(src)
    result.raise_for_status()

    filepath = Path("")
    if unzip:
        click.echo("Extracting zip file")
        with zipfile.ZipFile(io.BytesIO(result.content)) as zf:
            member = next(i for i in zf.filelist if is_godot_exectuable(i))
            zf.extract(member, dest_dir)
            filepath = Path(dest_dir) / Path(member.filename)
    else:
        with open(dest_dir / "godot", "wb") as f:
            f.write(result.content)
    return filepath


def get_versions(mirror) -> VersionsListData:
    versions = []
    home = TuxFamilySoup(mirror)
    directories = home.get_directories(is_version)
    with click.progressbar(
        directories.items(), label="Updating version database"
    ) as bar:
        for version, url in bar:
            details = TuxFamilySoup(url)
            directories = details.get_directories()
            if (data := get_version_data(version, "stable", directories)) is not None:
                versions.append(data)
            versions += get_flavor_data_list(version, "alpha", directories)
            versions += get_flavor_data_list(version, "beta", directories)
            versions += get_flavor_data_list(version, "rc", directories)
    return VersionsListData(versions)


def get_flavor_data_list(
    version: str, flavor: str, directories: dict[str, str]
) -> list[VersionData]:
    def flavors(base: str):
        i = 1
        while True:
            yield f"{base}{i}"
            i += 1

    data_list = []
    for i in flavors(flavor):
        if not i in directories:
            break
        flavor_soup = TuxFamilySoup(directories[i])
        flavor_dirs = flavor_soup.get_directories()
        if (data := get_version_data(version, i, flavor_dirs)) is not None:
            data_list.append(data)
    return data_list


def get_version_data(
    version: str, flavor: str, directories: dict[str, str]
) -> Optional[VersionData]:
    default_file = construct_filename(version, flavor, mono=False)
    if not default_file in directories:
        return None
    name = version if flavor == "stable" else f"{version}-{flavor}"
    channel = FLAVOR_MAPPING[FLAVOR_REGEX.sub("", flavor)]
    data = VersionData(name, channel, directories[default_file])
    if "mono" in directories:
        mono_soup = TuxFamilySoup(directories["mono"])
        mono_dirs = mono_soup.get_directories()
        mono_file = construct_filename(version, flavor, mono=True)
        if mono_file in mono_dirs:
            data.mono = mono_dirs[mono_file]
    return data


def construct_filename(version: str, flavor: str, mono: bool) -> str:
    typ = "mono_" if mono else ""
    join = "_" if mono else "."
    if version.startswith("1.") or version.startswith("2.0"):
        return f"Godot_v{version}_{flavor}_{typ}x11{join}64.zip"
    elif version.startswith("2.") or version.startswith("3."):
        return f"Godot_v{version}-{flavor}_{typ}x11{join}64.zip"
    elif version.startswith("4."):
        if flavor.startswith("alpha") and int(flavor[5:]) <= 14:
            return f"Godot_v{version}-{flavor}_{typ}linux{join}64.zip"
        else:
            return f"Godot_v{version}-{flavor}_{typ}linux{join}x86_64.zip"


def is_version(text: str) -> bool:
    return VERSION_REGEX.match(text) is not None


def is_godot_exectuable(info: zipfile.ZipInfo) -> bool:
    return (
        info.external_attr >> 16 & EXECUTABLE_BITS
        and "64" in info.filename.rsplit(".", 1)[-1]
    )
