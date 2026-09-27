import os
import pylast
import requests
import musicbrainzngs
from dotenv import load_dotenv

musicbrainzngs.set_useragent(
    "NextTrack",
    "1.0",
    "phan042@mymail.sim.edu.sg"
)
load_dotenv()

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")
LASTFM_API_ROOT = "https://ws.audioscrobbler.com/2.0/"

#get api key and secret from .env
lastfm_network = pylast.LastFMNetwork(
    api_key=LASTFM_API_KEY,
    api_secret=LASTFM_API_SECRET
)

#convert time data into mm:ss format
def format_length(length_ms):
    if not length_ms:
        return None

    seconds = int(length_ms) // 1000
    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"

def get_full_recording(recording_id):
    result = musicbrainzngs.get_recording_by_id(
        recording_id,
        includes=["artists", "releases", "tags", "url-rels", "work-rels"]
    )

    return result.get("recording", {})

# get links for preview
def get_music_links(song):
    links = []

    # make a list of avaliable links
    for rel in song.get("url-relation-list", []):
        url = rel.get("target")

        if url:
            links.append({
                "type": rel.get("type"),
                "url": url
            })

    return links

# use artist name and track title to search enrichment data from lastfm
def get_lastfm_data(artist_name, track_title):
    if not artist_name or not track_title:
        return {
            "listeners": None,
            "playcount": None,
            "tags": [],
            "lastfm_url": None
        }

    try:
        # getInfo to get link play count and listener count and tags
        # instead of calling them individually with pylast to save time
        response = requests.get(
            LASTFM_API_ROOT,
            params={
                "method": "track.getInfo",
                "artist": artist_name,
                "track": track_title,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "autocorrect": 1,
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise ValueError(data.get("message", "Last.fm API error"))

        track_data = data.get("track", {})

        listeners = track_data.get("listeners")
        playcount = track_data.get("playcount")
        lastfm_url = track_data.get("url")

        listeners = int(listeners) if listeners else None
        playcount = int(playcount) if playcount else None
        tag_data = track_data.get("toptags", {}).get("tag", [])

        if isinstance(tag_data, dict):
            tag_data = [tag_data]

        lastfm_tags = [
            tag.get("name")
            for tag in tag_data[:5]
            if tag.get("name")
        ]

        # use artist tags if the track has less than 5 tags
        if len(lastfm_tags) < 5:
            try:
                artist = lastfm_network.get_artist(artist_name)
                artist_tags = artist.get_top_tags(limit=5)

                for tag in artist_tags:
                    tag_name = tag.item.get_name()

                    if tag_name.lower() not in [t.lower() for t in lastfm_tags]:
                        lastfm_tags.append(tag_name)

                    if len(lastfm_tags) >= 5:
                        break

            except Exception as e:
                print(f"Artist tag fallback failed for '{artist_name}': {e}")

        return {
            "listeners": listeners,
            "playcount": playcount,
            "tags": lastfm_tags,
            "lastfm_url": lastfm_url
        }

    except Exception as e:
        print(f"Last.fm lookup skipped for '{track_title}' by '{artist_name}': {e}")

        return {
            "listeners": None,
            "playcount": None,
            "tags": [],
            "lastfm_url": None
        }

def enrich_with_lastfm(song_data):
    lastfm_data = get_lastfm_data(
        song_data.get("artist"),
        song_data.get("title")
    )

    song_data["listeners"] = lastfm_data["listeners"]
    song_data["playcount"] = lastfm_data["playcount"]

    musicbrainz_tags = song_data.get("combined_tags", [])
    lastfm_tags = lastfm_data["tags"]

    song_data["combined_tags"] = list(dict.fromkeys(
        musicbrainz_tags + lastfm_tags
    ))
    song_data["tags"] = song_data["combined_tags"]

    if lastfm_data["lastfm_url"]:
        song_data.setdefault("links", []).append({
            "type": "last.fm page",
            "url": lastfm_data["lastfm_url"]
        })

    return song_data

def format_musicbrainz_data(song):
    releases = song.get("release-list", [])
    first_release = releases[0] if releases else {}

    musicbrainz_language = next(
        (
            relation.get("work", {}).get("language")
            for relation in song.get("work-relation-list", [])
            if relation.get("work", {}).get("language")
        ),
        None
    )

    musicbrainz_tags = [
        tag.get("name")
        for tag in song.get("tag-list", [])
        if tag.get("name")
    ]

    return {
        "title": song.get("title"),
        "artist": song.get("artist-credit-phrase"),
        "length": format_length(song.get("length")),
        "mbid": song.get("id"),
        "release": first_release.get("title"),
        "language": musicbrainz_language,
        "links": get_music_links(song),
        "combined_tags": musicbrainz_tags,
    }

# get 4 other similar artists total 5
def get_similar_artists(artist_name, limit=4):
    if not artist_name:
        return []

    try:
        artist = lastfm_network.get_artist(artist_name)
        similar = artist.get_similar(limit=limit)

        return [
            {
                "name": item.item.get_name(),
                "match": float(item.match)
            }
            for item in similar
        ]

    except Exception as e:
        print(f"Similar artist lookup skipped for '{artist_name}': {e}")
        return []

# get tracks with last.fm, only if lang is provided
def get_tag_tracks(tag_name, limit=25, page=1):
    if not tag_name:
        return []

    try:
        response = requests.get(
            LASTFM_API_ROOT,
            params={
                "method": "tag.getTopTracks",
                "tag": tag_name,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": limit,
                "page": page,
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        tracks = []

        for item in data.get("tracks", {}).get("track", []):
            artist_data = item.get("artist", {})

            artist_name = artist_data.get("name")
            track_title = item.get("name")

            if artist_name and track_title:
                tracks.append({
                    "artist": artist_name,
                    "title": track_title
                })

        return tracks

    except Exception as e:
        print(f"Last.fm tag lookup skipped for '{tag_name}', page {page}: {e}")

        return []