import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Union

import yaml
from spotipy import Spotify, SpotifyException
from spotipy.oauth2 import SpotifyOAuth


def load_yaml_file(filepath: Path | str) -> dict[str, str]:
    script_dir: Path = Path(__file__).parent
    filepath: Path = script_dir / filepath
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


config: dict[str, str] = load_yaml_file("config.yaml")
logging.basicConfig(
    filename=config["log_filename"],
    encoding="utf-8",
    datefmt="%Y-%m-%d %H:%M:%S",
    format="%(asctime)s:%(levelname)s:%(message)s",
    level=logging.getLevelNamesMapping()[config["log_level"]],
)
logger: logging.Logger = logging.getLogger(__name__)


def get_saveable_tracks(
    spotify_client: Spotify, items: dict[str, Union[str, list, int, None]]
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
            print(queue_message)

            queued_tracks += 1
        if items["next"]:
            items = spotify_client.next(items)
        else:
            break

    return {
        "tracks": tracks,
        "track_count": track_count,
        "queued_tracks": queued_tracks,
    }


def get_formatted_track_number(queued_tracks: int, track_count: int) -> str:
    return f"{str((queued_tracks + 1)).rjust(len(str(track_count)))}/{track_count}"


def get_track_artist_names(track: dict[str]) -> list[str]:
    return [track["artists"][i]["name"] for i, _ in enumerate(track["artists"])]


def get_track_info_appendix(track: dict[str]) -> str:
    track_artists: list = get_track_artist_names(track)
    track_name: str = track["name"]
    if list(filter(lambda i: i, track_artists)) and list(
        filter(lambda i: i, track_name)
    ):
        return f': {", ".join(track_artists)} - {track_name}'
    return ""


def save_tracks(
    spotify_client: Spotify, tracks: dict[str:list, str:int, str:int]
) -> tuple[int, int]:
    tracks_saved: int = 0
    error_count: int = 0
    track_id: str | None = None
    for i, track in enumerate(tracks["tracks"], 1):
        track_id = track["id"]
        try:
            formatted_track_number = get_formatted_track_number(
                i, len(tracks["tracks"])
            )
            track_info_appendix: str = get_track_info_appendix(track)
            if spotify_client.current_user_saved_tracks_contains([track_id])[0]:
                message: str = (
                    f"{formatted_track_number} Track with ID {track_id} already saved"
                    f"{track_info_appendix}"
                )
                print(message)
                logging.info(message)
                continue
            spotify_client.current_user_saved_tracks_add([track_id])
            message = (
                f"{formatted_track_number} Saved track with ID {track_id}"
                f"{track_info_appendix}"
            )
            print(message)
            logging.info(message)
            tracks_saved += 1
        except SpotifyException as exception:
            message: str = f"Error saving track with ID {track_id}"
            print(message)
            logging.error("%s:%s", message, exception)
            error_count += 1

    return tracks_saved, error_count


def main() -> None:
    auth_manager: SpotifyOAuth = SpotifyOAuth(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri="https://github.com/Temerold/heart-all/",
        scope=["user-library-read", "user-library-modify"],
    )
    spotify_client: Spotify = Spotify(auth_manager=auth_manager)
    if not (playlist_id := config["playlist_id"]):
        playlist_id: str = input("ID of playlist to forcibly save: ")
    try:
        items: dict = spotify_client.playlist_items(playlist_id)
    except SpotifyException:
        # pylint: disable=line-too-long
        logging.error(
            "Playlist ID %s possibly invalid. See "
            "https://developer.spotify.com/documentation/web-api/concepts/spotify-uris-ids",
            playlist_id,
        )
        # pylint enable=line-too-long
        return

    saveable_tracks: Mapping[str, Union[list, int]] = get_saveable_tracks(
        spotify_client, items
    )
    tracks_saved, error_count = save_tracks(spotify_client, saveable_tracks)
    tracks_saved: int
    error_count: int

    appendix: str = (
        f" Forcibly saved {tracks_saved}/" f"{saveable_tracks["queued_tracks"]} tracks"
    )

    if error_count:
        print(
            f"Finished with {error_count} errors. See logs for more information."
            + appendix
        )
    else:
        print(f"Finished without errors.{appendix}")
    print()


if __name__ == "__main__":
    main()
