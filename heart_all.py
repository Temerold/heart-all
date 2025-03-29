"""
This script uses the Spotify API to save tracks from a playlist to the user's library.

Its canonical open-source location is:
https://github.com/Temerold/heart-all/blob/main/heart_all.py
"""

import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Union

import yaml
from dotenv import dotenv_values
from spotipy import Spotify, SpotifyException
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth


def excepthook(
    logger: logging.Logger,
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(type, exc_value, exc_traceback)


def get_formatted_track_number(queued_tracks: int, track_count: int) -> str:
    return f"{str((queued_tracks + 1)).rjust(len(str(track_count)))}/{track_count}"


def get_saveable_tracks(
    spotipy_client: Spotify, items: dict[str, Union[str, list, int, None]]
) -> Mapping[str, Union[list, int]]:
    tracks: list[dict] = []
    track_count: int = items["total"]
    queued_tracks: int = 0
    while items:
        for item in items["items"]:
            track: dict | None = item.get("track")
            if track is None or track.get("id") is None:
                continue
            tracks.append(track)

            formatted_track_number = get_formatted_track_number(
                queued_tracks, track_count
            )
            track_info_appendix: str = get_track_info_appendix(track)
            queue_message: str = (
                f"{formatted_track_number} Queued track with ID {track["id"]}"
                f"{track_info_appendix}"
            )
            logging.info(queue_message)

            queued_tracks += 1

        if not items["next"]:
            break
        items = spotipy_client.next(items)

    return {
        "tracks": tracks,
        "track_count": track_count,
        "queued_tracks": queued_tracks,
    }


def get_spotipy_client(scope: list[str] = None) -> Spotify:
    if scope is None:
        scope = ["user-library-read", "user-library-modify"]

    if Path.exists(Path(__file__).parent / ".cache"):
        auth_manager = SpotifyOAuth(
            client_id=" ", client_secret=" ", redirect_uri=" ", scope=scope
        )
        valid, exception = validate_spotipy_client(auth_manager)
    else:
        valid: bool = False

    env_vars: dict = get_spotipy_client_env_vars()
    if not valid:  # `.cache` is either missing or invalid
        if not env_vars["SPOTIPY_CLIENT_ID"]:
            env_vars["SPOTIPY_CLIENT_ID"] = input(
                "Please input Spotify application client ID: "
            )

        if not env_vars["SPOTIPY_CLIENT_SECRET"]:
            env_vars["SPOTIPY_CLIENT_SECRET"] = input(
                "Please input Spotify application client secret: "
            )

        if not env_vars["SPOTIPY_REDIRECT_URI"]:
            env_vars["SPOTIPY_REDIRECT_URI"] = input(
                "Please input Spotify application redirect URI: "
            )

    auth_manager = SpotifyOAuth(
        client_id=env_vars["SPOTIPY_CLIENT_ID"] or " ",
        client_secret=env_vars["SPOTIPY_CLIENT_SECRET"] or " ",
        redirect_uri=env_vars["SPOTIPY_REDIRECT_URI"] or " ",
        scope=scope,
    )
    valid, exception = validate_spotipy_client(auth_manager)
    valid: bool
    exception: Exception | None
    if not valid:
        message: str = "Invalid Spotify application credentials."
        logging.error(message, exc_info=exception)
        print(message)
        sys.exit(1)

    return Spotify(auth_manager=auth_manager)


def get_spotipy_client_env_vars() -> Spotify:
    return {
        "SPOTIPY_CLIENT_ID": env_secrets.get("SPOTIPY_CLIENT_ID"),
        "SPOTIPY_CLIENT_SECRET": env_secrets.get("SPOTIPY_CLIENT_SECRET"),
        "SPOTIPY_REDIRECT_URI": env_secrets.get("SPOTIPY_REDIRECT_URI"),
    }


def get_track_artist_names(track: dict[str]) -> list[str]:
    return [track["artists"][i]["name"] for i, _ in enumerate(track["artists"])]


def get_track_info_appendix(track: dict[str]) -> str:
    track_artists: list[str] = get_track_artist_names(track)
    track_name: str = track["name"]
    if list(filter(lambda i: i, track_artists)) and list(
        filter(lambda i: i, track_name)
    ):
        return f": {", ".join(track_artists)} - {track_name}"
    return ""


def load_config_and_environment() -> None:
    global env_secrets, config

    env_secrets = dotenv_values(".env")
    config = None
    for file in (recognized_config_files := ["config.yaml", "config.yml"]):
        if Path.exists(Path(__file__).parent / file):
            config = load_yaml_file(file)

    if not config:
        raise FileNotFoundError(
            f"Config file not found. Expected one of the following: "
            f"{", ".join(recognized_config_files)}"
        )

    logging.basicConfig(
        filename=config["log_filename"],
        encoding="utf-8",
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s:%(levelname)s:%(message)s",
        level=20,
    )
    logging.info = logging_info_override
    logger: logging.Logger = logging.getLogger(__name__)
    sys.excepthook = lambda type, value, traceback: excepthook(
        logger, type, value, traceback
    )


def load_yaml_file(filepath: Path | str) -> dict[str, str]:
    script_dir: Path = Path(__file__).parent
    filepath: Path = script_dir / filepath
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def logging_info_override(
    message: str, *args, terminal_output: bool = True, **kwargs
) -> None:
    logging.getLogger().log(20, message, *args, **kwargs)
    if terminal_output:
        print(message % args if args else message)


def save_tracks(
    spotipy_client: Spotify, tracks: dict[str:list, str:int, str:int]
) -> tuple[int, int]:
    tracks_saved: int = 0
    error_count: int = 0
    track_id: str | None = None
    for i, track in enumerate(tracks["tracks"]):
        track_id = track["id"]
        try:
            formatted_track_number = get_formatted_track_number(
                i, len(tracks["tracks"])
            )
            track_info_appendix: str = get_track_info_appendix(track)
            if spotipy_client.current_user_saved_tracks_contains([track_id])[0]:
                message: str = (
                    f"{formatted_track_number} Track with ID {track_id} already saved"
                    f"{track_info_appendix}"
                )
                logging.info(message)
                continue

            spotipy_client.current_user_saved_tracks_add([track_id])

            message = (
                f"{formatted_track_number} Saved track with ID {track_id}"
                f"{track_info_appendix}"
            )
            logging.info(message)

            tracks_saved += 1
        except SpotifyException as exception:
            message: str = f"Error saving track with ID {track_id}"
            logging.error(message, exc_info=exception)

            error_count += 1

    return tracks_saved, error_count


def validate_spotipy_client(
    auth_manager: SpotifyOAuth,
) -> tuple[bool, Union[Exception, None]]:
    try:
        Spotify(auth_manager=auth_manager).current_user()
        return True, None
    except SpotifyOauthError as exception:
        return False, exception


def main() -> None:
    spotipy_client: Spotify = get_spotipy_client()
    logging.info(
        "Successfully authenticated with Spotify as user %s",
        spotipy_client.current_user()["display_name"],
    )

    if not (playlist_id := config["playlist_id"]):
        playlist_id: str = input("Please input ID of playlist to forcibly save: ")

    try:
        items: dict = spotipy_client.playlist_items(playlist_id)
    except SpotifyException as exception:
        # pylint: disable=line-too-long
        message = (
            f"Playlist ID {playlist_id} possibly invalid. See "
            "https://developer.spotify.com/documentation/web-api/concepts/spotify-uris-ids"
        )
        # pylint enable=line-too-long
        logging.error(message, exc_info=exception)
        print(message)
        return

    saveable_tracks: Mapping[str, Union[list, int]] = get_saveable_tracks(
        spotipy_client, items
    )
    tracks_saved, error_count = save_tracks(spotipy_client, saveable_tracks)
    tracks_saved: int
    error_count: int

    appendix: str = (
        f" Forcibly saved {tracks_saved}/" f"{saveable_tracks["queued_tracks"]} tracks"
    )
    if error_count:
        absolute_log_filename: str = Path(config["log_filename"]).absolute()
        logging.info(
            "Finished with %d errors. See logs for more information: %s%s",
            error_count,
            absolute_log_filename,
            appendix,
        )
    else:
        logging.info("Finished without errors.%s", appendix)


if __name__ == "__main__":
    env_secrets: dict
    config: dict
    load_config_and_environment()
    main()
