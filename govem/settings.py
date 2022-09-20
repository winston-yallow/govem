from dataclasses import dataclass
from pathlib import Path


# TODO: Use configparser for this.
# This was created at 3am in the morning and is not a good idea.
# It is just a placeholder for actual settings. The settings should
# be loaded from a file in XDG_CONFIG_DIR or HOME. Each setting
# should be overridable with an env var
# The purpose of this file is to load the settings once and provide
# them to the rest of the govem application.
# I think it could be nice to have the individual setting as toplevel
# variables here instead of in a class. It may not be best practice,
# but it will be fine for such a small application as govem. And it
# for sure makes accessing the settings nicer.


@dataclass
class SettingsData:
    mirror: str
    cache_path: str  # Dir to store cached data (like version list)
    data_path: str  # Dir to store installations
    bin_path: str  # Dir to symlink binaries in (should be a location in PATH)
    desktopfile_install: bool = True
    versions_file: str = "versions.json"
    executable_file: str = "godot"
    info_file: str = "info.json"
    selected_file: str = "selected.txt"

    # TODO: Instead of having resolve methods, we can directly resolve
    # the base path when loading the settings.
    def resolve_cachepath(self, name: str) -> Path:
        return (Path.cwd() / Path(self.cache_path)).resolve() / Path(name)

    def resolve_datapath(self, name: str) -> Path:
        return (Path.cwd() / Path(self.data_path)).resolve() / Path(name)

    def resolve_binpath(self, name: str) -> Path:
        return (Path.cwd() / Path(self.bin_path)).resolve() / Path(name)


def load_settings() -> SettingsData:
    return SettingsData(
        "https://downloads.tuxfamily.org/godotengine/",
        ".cache",
        ".data",
        ".shims",
        True,
    )


# This acts as globally usable object to access the settings
data = load_settings()
