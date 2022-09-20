import re
import sys
from pathlib import Path

import click

from . import download, installation, settings


def is_valid_name(ctx, param, value):
    """
    Small helper function that validates names for installations.
    It allows numbers, characters a-z as well as dot, hypen and underscore.
    This is to be used as a callback for a click argument.
    """
    # TODO: We can make this less strict to allow all characters that are
    # valid within directory names.
    if value is None or re.match(r"^[\-\_\.\w\d]+$", value):
        return value
    else:
        raise click.BadParameter(
            "Only alphanumeric characters and dots, hyphens and underscores are allowed"
        )


def exclusive(args: list[str]):
    """
    This method generates a callback to ensure that the given args are not used
    together. The returned method is to be used as a callback for a click option.
    """

    def check(ctx, param, value):
        if value is not None:
            for k, v in ctx.params.items():
                if k in args and v is not None:
                    raise click.BadParameter(
                        "The options --local-file, --download-zip and --download-file are mutually exclusive"
                    )
        return value

    return check


def get_version_url(version: str, mono: bool) -> str:
    """
    Get the URL for a given version from the cached data. Shows an
    error message and exits the whole process if version is invalid.
    """
    versions_file = settings.data.resolve_cachepath(settings.data.versions_file)
    data = download.VersionsListData.from_json_file(versions_file)
    try:
        version_data = next(i for i in data.versions if i.name == version)
        url = version_data.mono if mono else version_data.default
    except StopIteration:
        click.secho(f'Could not find "{version}"', fg="red")
        click.echo(
            'Make sure the version database is not outdated. Try running "govem update".'
        )
        sys.exit(1)
    return url


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--unstable/--stable",
    "-u",
    default=False,
    help="Decide whether unstable versions (alphas, betas and release candidates) should be shown.",
)
@click.argument("filter", type=str, default="")
def versions(unstable, filter):
    """
    Show a (filtered) list of available versions.

    If FILTER is given, then only versions starting with the filter will be listed.
    """
    versions_file = settings.data.resolve_cachepath(settings.data.versions_file)
    data = download.VersionsListData.from_json_file(versions_file)
    last_major = ""
    for version in data.versions:
        # Skip if unstable but user only wants stable versions
        if version.channel != download.VersionData.CHANNEL_STABLE and not unstable:
            continue
        # Skip if filter doesn't match
        if not version.name.startswith(filter):
            continue
        # Show version (and major category if it changed)
        major = version.name[: version.name.find(".")]
        if last_major != major:
            last_major = major
            click.secho(f"\nGodot {major}", fg="blue")
        click.echo("  " + version.name)


@cli.command()
def update():
    """
    Update the internal list of available versions.
    """
    data = download.get_versions(settings.data.mirror)
    versions_file = settings.data.resolve_cachepath(settings.data.versions_file)
    versions_file.parent.mkdir(parents=True, exist_ok=True)
    data.to_json_file(versions_file)
    click.echo(f"Writing data to {versions_file}")


# Only one source can be used at a time, otherwise it is considered invalid
is_valid_source = exclusive(["local_file", "download_zip", "download_file"])


@cli.command()
@click.option(
    "--name",
    "-n",
    type=str,
    callback=is_valid_name,
    help="Custom name for the installation (defaults to version string)",
)
@click.option(
    "--mono/--standard",
    "-m",
    default=False,
    help="Pick between mono or standard version",
)
@click.option(
    "--force",
    "-f",
    default=False,
    is_flag=True,
    help="Force installation even if another installation uses the same name",
)
@click.option(
    "--local-file",
    "-l",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True),
    callback=is_valid_source,
    help="Use local file as godot executable",
)
@click.option(
    "--download-zip",
    "-z",
    type=str,
    callback=is_valid_source,
    help="Use custom URL to zip file to download and extract",
    metavar="URL",
)
@click.option(
    "--download-file",
    "-d",
    type=str,
    callback=is_valid_source,
    help="Use custom URL to executable file to download",
    metavar="URL",
)
@click.argument("version", type=str, callback=is_valid_name)
def install(name, mono, force, local_file, download_zip, download_file, version):
    """
    Install godot for the current user.
    """
    # Yes, this function is a bit convoluted, but it works ¯\_(ツ)_/¯
    print("")
    name = version if not name or name.isspace() else name
    try:
        if local_file:
            # Install local file
            filepath = Path(local_file).resolve()
            data = installation.InstallData(
                installation.TYPE_LOCAL_FILECOPY, str(filepath)
            )
            installation.install_file(name, data, filepath, force)
        else:
            # Set url and unzip setting
            if download_file:
                unzip = False
                url = download_file
            elif download_zip:
                unzip = True
                url = download_zip
            else:
                unzip = True
                url = get_version_url(version, mono)
            # Perform installation
            installation.install_download(name, url, unzip, force)
        click.secho(f"Successfully installed Godot {name}", fg="green")
    except installation.InstallationExistsError:
        click.secho(f'Installation with name "{name}" already exists', fg="red")
        click.echo("If you want to overwrite existing files run command with --force.")
        click.echo("Alternatively you can specify a different name with --name.")


@cli.command()
def list():
    """
    List all existing godot installations.
    """
    selected_file = settings.data.resolve_datapath(settings.data.selected_file)
    if selected_file.exists():
        with open(selected_file, "r") as f:
            selected = f.read()
    else:
        selected = ""

    click.echo("\nInstalled versions:")
    for path in settings.data.resolve_datapath("").iterdir():
        # Skip entries that aren't a version directory
        if not path.is_dir():
            continue
        # Create basic description
        text = "  ● " if path.name == selected else "  ◯ "
        text += click.style(path.name, fg="blue")
        info_file = path / settings.data.info_file
        # Add source information if it exists
        if info_file.exists():
            info = installation.InstallData.from_json_file(info_file)
            typ = installation.TYPE_DESCRIPTIONS[info.typ]
            text += f" ({typ})"
        else:
            text += click.style(" (no info available)", fg="red")
        # Add badge if the version is currently selected
        if path.name == selected:
            text += click.style(" [selected]", fg="green")
        # Show the text
        click.echo(text)


@cli.command()
@click.argument("name", type=str, callback=is_valid_name)
def select(name):
    """
    Select a specific godot version.
    This will make the `godot` command point to that version.

    NAME must be the name of an existing godot installation.
    """
    try:
        installation.select(name)
        click.secho(f"Successfully selected Godot {name}", fg="green")
    except installation.InstallationMissingError:
        click.secho(f'No installation named "{name}" exists.', fg="red")


@cli.command()
@click.argument("name", type=str, callback=is_valid_name)
def uninstall(name):
    """
    Uninstall a specific godot installation.

    NAME must be the name of an existing godot installation.
    """
    print("")
    try:
        installation.uninstall(name)
        click.secho(f"Successfully removed Godot {name}", fg="green")
    except installation.InstallationMissingError:
        click.secho(f'No installation named "{name}" exists.', fg="red")
