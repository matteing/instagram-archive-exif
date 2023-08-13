import argparse
import json
import os
import shutil
import exiftool
import logging
import html
import pathlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.logging import RichHandler
from rich.pretty import pprint

VERBOSE = False
console = Console()

CONTENT_TYPE_KEYS = [
    "ig_archived_post_media",
    "ig_stories",
    "ig_profile_picture",
    "ig_recently_deleted_media",
]

FORMAT = "%(message)s"
if VERBOSE:
    logging.basicConfig(
        level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
    )


@dataclass
class ImageFile:
    content_type: str
    path: str
    title: Optional[str]
    created_at: datetime
    exif_data: dict


def unix_timestamp_to_datetime(unix_timestamp):
    try:
        timestamp = datetime.fromtimestamp(unix_timestamp)
        formatted_datetime = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_datetime
    except OSError:
        return "Invalid timestamp"


def to_exif_datetime(datetime: datetime) -> str:
    return datetime.strftime("%Y:%m:%d %H:%M:%S")


def get_exif_data_for_entry(entry: dict) -> dict:
    return (
        entry.get("media_metadata", {}).get("photo_metadata", {}).get("exif_data", {})
    )


def get_timestamp_for_entry(entry: dict) -> datetime:
    timestamp = entry.get("creation_timestamp", None)
    return datetime.fromtimestamp(timestamp) if timestamp else datetime.now()


def get_path_for_entry(entry: dict, archive_path: str) -> str:
    # sometimes the archive is a... URL?!
    if "uri" not in entry or not entry["uri"] or entry["uri"] == "" or "https://" in entry["uri"]:
        return None
    base_path = pathlib.Path(archive_path)
    return str(base_path / entry["uri"]).split("?")[0]


def get_metadata_for_content_types(
    parsed_json: dict, base_archive_path: str
) -> list[ImageFile]:
    metadata = []
    for content_type in CONTENT_TYPE_KEYS:
        if not content_type in parsed_json:
            continue
        for entry in parsed_json[content_type]:
            parent_entry_title = entry.get("title", None)
            if "media" in entry:
                # This is a multi-picture post
                # Grab the title from the parent
                for media in entry["media"]:
                    title = media.get("title", None)
                    title = (
                        title.encode("latin-1").decode("utf-8")
                        if title and title != ""
                        else parent_entry_title
                    )
                    path = get_path_for_entry(media, base_archive_path)
                    file = ImageFile(
                        content_type,
                        path,
                        title,
                        get_timestamp_for_entry(media),
                        get_exif_data_for_entry(media),
                    )
                    if file.path and file.path != "":
                        metadata.append(file)
            else:
                path = get_path_for_entry(entry, base_archive_path)
                file = ImageFile(
                    content_type,
                    path,
                    parent_entry_title.encode("latin-1").decode("utf-8")
                    if parent_entry_title
                    else None,
                    get_timestamp_for_entry(entry),
                    get_exif_data_for_entry(entry),
                )
                if file.path and file.path != "":
                  metadata.append(file)
    return metadata


def display_operation_preview(image_files: list[ImageFile]) -> None:
    table = Table(title="Files to process")
    table.add_column("Path", justify="right", style="cyan", no_wrap=True)
    table.add_column("Title", style="magenta")
    table.add_column("Timestamp", justify="right", style="green")
    image_files.sort(key=lambda x: x.created_at)
    for item in image_files:
        # Get the first two directories in the path
        uri = "/".join(item.path.split("/")[:2])
        # Trim the title if it's too long
        title = "Untitled"
        if item.title:
            title = item.title[:40] + "..." if len(item.title) > 20 else item.title
        # Convert to ASCII
        title = title
        table.add_row(uri, title, to_exif_datetime(item.created_at))
    console.print(table)


def get_exif_tags(file: ImageFile) -> dict:
    tags = {
        "AllDates": to_exif_datetime(file.created_at),
    }
    if "latitude" in file.exif_data and "longitude" in file.exif_data:
        tags["GPSLatitude"] = file.exif_data["latitude"]
        tags["GPSLongitude"] = file.exif_data["longitude"]
    if "iso" in file.exif_data:
        tags["ISO"] = file.exif_data["iso"]
    if "lens_make" in file.exif_data:
        tags["LensMake"] = file.exif_data["make"]
    if "lens_model" in file.exif_data:
        tags["LensModel"] = file.exif_data["model"]
    if "scene_type" in file.exif_data:
        tags["SceneType"] = file.exif_data["scene_type"]
    if "aperture" in file.exif_data:
        tags["ApertureValue"] = file.exif_data["aperture"]
    if "shutter_speed" in file.exif_data:
        tags["ShutterSpeedValue"] = file.exif_data["shutter_speed"]
    if "focal_length" in file.exif_data:
        tags["FocalLength"] = file.exif_data["focal_length"]
    if "metering_mode" in file.exif_data:
        tags["MeteringMode"] = file.exif_data["metering_mode"]
    if file.title and file.title != "":
        # tags["iptc:Caption-Abstract"] = f'"{html.escape(file.title)}"'
        tags["iptc:Keywords"] = "Instagram"
        # tags["iptc:ObjectName"] = f'"{html.escape(file.title)}"'
        tags["iptc:OriginatingProgram"] = "Instagram"
        tags["iptc:codedcharacterset"] = "utf8"
    return tags


def process_files(image_files: list[ImageFile], archive_path: str) -> None:
    exiftool_executable = shutil.which("exiftool")
    if exiftool_executable is None:
        console.print("Error: exiftool not found in PATH.")
        exit(1)
    with exiftool.ExifToolHelper(logger=logging.getLogger("rich")) as et:
        with Progress() as progress:
            task = progress.add_task("Processing files...", total=len(image_files))
            for file in image_files:
                # Set the output path, get the original extension using pathlib.
                filename = pathlib.Path(file.path).stem
                extension = pathlib.Path(file.path).suffix
                username = os.path.basename(archive_path)
                result_path = (
                    pathlib.Path(pathlib.Path.cwd())
                    / f"result/{username}/{file.content_type}/{filename}{extension}"
                )
                # Create result path
                os.makedirs(os.path.dirname(result_path), exist_ok=True)
                shutil.copy(file.path, result_path)
                try:       
                  et.set_tags(
                      [result_path], get_exif_tags(file), params=["-overwrite_original"]
                  )
                except:
                  progress.log(f"[bold red]Exiftool quit while processing {file.path}.[/]")
                os.utime(
                    result_path,
                    (file.created_at.timestamp(), file.created_at.timestamp()),
                )
                progress.advance(task)


def process_json_file(json_file):
    try:
        # Get the root of the archive (2 folders up from the JSON file)
        base_archive_path = pathlib.Path(json_file).parent.parent.absolute()
        console.print(f"Archive found at {base_archive_path}")
        should_exit = console.input("Is this correct? [Y/n]") == "n"
        if should_exit:
            exit(0)
        with open(json_file, "r", encoding="utf-8") as file:
            data = json.load(file)
            files = get_metadata_for_content_types(data, base_archive_path)
            display_operation_preview(files)
            should_exit = input("Continue? [Y/n]") == "n"
            if should_exit:
                exit(0)
            process_files(files, base_archive_path)
    except FileNotFoundError:
        print("Error: JSON file not found.")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format.")


def main():
    parser = argparse.ArgumentParser(
        description="Uses an Instagram 'content' JSON file to assign EXIF data. Should run from the root of your export."
    )
    parser.add_argument("arguments", nargs="*", help="Paths of JSON files to process.")
    args = parser.parse_args()

    for path in args.arguments:
        process_json_file(path)

if __name__ == "__main__":
    main()
