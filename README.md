# GOVEM - Godot Version Manager

## About
Small command line tool to manage godot versions.

### Features
- fetch available downloads from tuxfamily.org
- download and install godot (creating desktopfile and adding the executable to the path)
- install from local file (for example a local build)
- keep installed versions separate by using self-contained mode
- configurable which installation the `godot` command should use


### What this isn't
- project manager (if you are looking for one, try
  [Hourglass](https://hourglass.jwestman.net/))
- build tool (godot uses scons which is nice to use on it's own)
- project launcher (godot installations are added to the path and to the start menu, so
  use system tools to start stuff)
- cross-platform (I use linux, if anyone wants to contribute other platforms I am more
  than happy to add them!)

## Usage
This project currently uses [poetry](https://python-poetry.org/).
There is no nice way yet to install `govem`, but here is how to test and develop it:

### Commands
```bash
# Setup your local workspace with poetry. This will automatically create a venv
poetry install

# Run govem
poetry run govem --help

# Run black (used for consistent code-formatting)
poetry run black
```

### Configuration
There is no config file yet. All settings are stored in `settings.py`. It is planned
to add support for proper configs. For now just modify that file, but take care to
not commit your local adjustments.

Defaults currently are mostly relative to the project directory (since that makes
development a bit nicer).

With no changes, these are the used directories:
- `$PROJECT/.config/` directory used to store cached list of available godot downloads
- `$PROJECT/.data/` directory where persistent data is stored (godot installations etc)
- `$PROJECT/.shims/` directory where symlinks are created for each installation (in an
  actual real-life scenario you would set this to a directory in your `$PAHT` like for
  example `~/.local/bin`)
- `$HOME/.local/share/applications` this is the only directory not relative to the
  project directory. This one is the standard XDG dir for local installations and
  currently not configurable. You can turn of installation of desktopfiles though by
  setting `SettingsData.desktopfile_install` to `False`)

## Contributing
I welcome all contributions, but please coordinate with me first before doing anything.
I have quite some changes planned out already, so it would be good to first check with
me what I have in mind. That way we prevent work being done that has no chance of being
merged.

## Roadmap
This is still in the early stages. I initially did this as a small proof-of-concept for
a minimal manager for godot installations. It turned out quite nicely, so I'm putting
this out for other people to use. The code may not be the best quality (though I tried
to at least clean it up a bit), but it's a foundation that can be worked with. That
being said, here are some things I want to add over the next months:
- create proper configfile with sensible defaults for settings
- use setuptools (it makes it easy to run `govem` inside a venv without explictly
  activating the venv, which will also help with making govem easy to install)
- refactor the downloading code (especialy make it work with mono versions)
- make directory for desktopfile installations configurable
- add `govem refresh` subcommand for re-downloading or re-copying files for the
  installation
- create a nice looking logo, preferably one that works as ASCII art
- transfer this roadmap from the readme to actual actionable and detailed github issues

## License
This project uses the MIT License.
