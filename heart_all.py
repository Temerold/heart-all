import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Union

import yaml
from dotenv import dotenv_values
from spotipy import Spotify, SpotifyException
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth


def excepthook(logger, type, value, traceback):
    logger.error("Uncaught exception", exc_info=(type, value, traceback))
    sys.__excepthook__(type, value, traceback)


def load_yaml_file(filepath: Path | str) -> dict[str, str]:
    script_dir: Path = Path(__file__).parent
    filepath: Path = script_dir / filepath
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def logging_info_override(message, terminal_output=True, *args, **kwargs):
    logging.getLogger().log(20, message, *args, **kwargs)
    if terminal_output:
        print(message)


env_secrets = dotenv_values(".env")
config: dict[str, str] = load_yaml_file("config.yaml")
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


def get_formatted_track_number(queued_tracks: int, track_count: int) -> str:
    return f"{str((queued_tracks + 1)).rjust(len(str(track_count)))}/{track_count}"


def get_saveable_tracks(
    spotipy_client: Spotify, items: dict[str, Union[str, list, int, None]]
) -> Mapping[str, Union[list, int]]:
    tracks: list = []
    track_count: int = items["total"]
    queued_tracks: int = 0
    while items:
        for item in items["items"]:
            track: dict | None = item["track"]
            if not (track and "id" in track and track["id"]):
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


def get_spotipy_client(
    scope: list[str] = ["user-library-read", "user-library-modify"]
) -> Spotify:
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
    track_artists: list = get_track_artist_names(track)
    track_name: str = track["name"]
    if list(filter(lambda i: i, track_artists)) and list(
        filter(lambda i: i, track_name)
    ):
        return f": {", ".join(track_artists)} - {track_name}"
    return ""


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
        f"Successfully authenticated with Spotify as user "
        f"{spotipy_client.current_user()["display_name"]}"
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
            f"Finished with {error_count} errors. See logs for more information: "
            f"{absolute_log_filename}{appendix}"
        )
    else:
        logging.info(f"Finished without errors.{appendix}")


if __name__ == "__main__":
    main()
