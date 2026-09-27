from django.shortcuts import render
import random
import musicbrainzngs
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .apiCalls import (
    get_full_recording,
    format_musicbrainz_data,
    enrich_with_lastfm,
    get_similar_artists,
    get_tag_tracks,
)

from .ranking import (
    calculate_metadata_scores,
    calculate_relevance_score,
    calculate_popularity_score,
    calculate_final_score,
    select_diverse_shortlist,
    rerank_for_diversity,
    normalise_text,
    normalise_title_for_dupes,
)

def home(request):
    song_data = None

    if request.GET.get("random"):
        result = musicbrainzngs.search_recordings(
            query="tag:j-pop",
            limit=25
        )

        recordings = result.get("recording-list", [])

        if recordings:
            song = random.choice(recordings)

            song_data = {
                "title": song.get("title"),
                "artist": song.get("artist-credit-phrase"),
                "length": song.get("length"),
            }

    return render(request, "musicRec/home.html", {"song": song_data})

def build_search_queries(artist, tags, title_keywords, include_similar_artists):
    match_parts = []
    similar_artists = []
    candidate_artists = []

    if artist:
        candidate_artists = [artist]
        # only if similar artists option selected
        if include_similar_artists:
            similar_artists = get_similar_artists(artist, limit=4)
            candidate_artists.extend(item["name"] for item in similar_artists)

    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        for tag in tag_list:
            match_parts.append(f'tag:"{tag}"')

    if title_keywords:
        match_parts.append(f'recording:"{title_keywords}"')

    return match_parts, similar_artists, candidate_artists

def search_musicbrainz_candidates(artist, candidate_artists, match_parts, candidate_limit):
    recordings = []
    filter_count = len(match_parts)

    if artist:
        per_artist_limit = max(1, candidate_limit // len(candidate_artists))

        for candidate_artist in candidate_artists:
            artist_query = f'artist:"{candidate_artist}"'

            if filter_count >= 2:
                query = artist_query + " AND (" + " OR ".join(match_parts) + ")"
            else:
                query = artist_query

            result = musicbrainzngs.search_recordings(query=query, limit=per_artist_limit)
            artist_recordings = result.get("recording-list", [])
            recordings.extend(artist_recordings)

    elif match_parts:
        query = " OR ".join(match_parts)
        result = musicbrainzngs.search_recordings(query=query, limit=candidate_limit)
        recordings.extend(result.get("recording-list", []))

    return recordings

def search_language_candidates(language_list, artist, candidate_artists, target_candidates):
    recordings = []
    page = 1
    max_pages = 3
    seen_language_tracks = set()
    seen_mb_songs = set()

    # search multiple Last.fm pages until enough unique songs are found
    while page <= max_pages and len(seen_mb_songs) < target_candidates:
        language_tracks = []

        if language_list:
            per_language_limit = max(1, 25 // len(language_list))
            for lang in language_list:
                language_tracks.extend(get_tag_tracks(lang, limit=per_language_limit, page=page))

        if artist:
            # keep tracks from the original artist and allowed similar artists
            allowed_artists = {normalise_text(name) for name in candidate_artists}
            language_tracks = [
                item for item in language_tracks
                if any(allowed in normalise_text(item.get("artist")) for allowed in allowed_artists)
            ]

        language_queries = []

        # remove duplicated artist and title combination
        for item in language_tracks:
            key = (normalise_text(item["artist"]), normalise_text(item["title"]))

            if key in seen_language_tracks:
                continue

            seen_language_tracks.add(key)

            artist_name = item["artist"].replace('"', '\\"')
            track_title = item["title"].replace('"', '\\"')

            language_queries.append(f'(artist:"{artist_name}" AND recording:"{track_title}")')

        if language_queries:
            batch_size = 15
            language_batch_limit = 30

            for i in range(0, len(language_queries), batch_size):
                batch = language_queries[i:i + batch_size]

                language_result = musicbrainzngs.search_recordings(
                    query=" OR ".join(batch),
                    limit=language_batch_limit
                )

                for song in language_result.get("recording-list", []):
                    artist_name = normalise_text(song.get("artist-credit-phrase"))
                    title = normalise_title_for_dupes(song.get("title"))
                    song_key = (artist_name, title)

                    if artist_name and title and song_key not in seen_mb_songs:
                        seen_mb_songs.add(song_key)
                        recordings.append(song)

                if len(seen_mb_songs) >= target_candidates:
                    break

        page += 1

    return recordings

def get_metadata_scores(song, artist, language, tags, title_keywords, similar_artists):
    metadata_scores = calculate_metadata_scores(
        song,
        artist,
        language,
        tags,
        title_keywords,
        similar_artists
    )

    relevance_score = calculate_relevance_score(metadata_scores)

    active_scores = [score for score in metadata_scores.values() if score is not None]
    metadata_match = sum(active_scores) / len(active_scores) if active_scores else 0

    return metadata_scores, relevance_score, metadata_match

def score_candidates(recordings, artist, language, tags, title_keywords, similar_artists):
    recommendations = []
    # track id and artist+title combination to avoid duplicated recommmedation
    seen_recording_ids = set()
    seen_songs = set()

    for song in recordings:
        recording_id = song.get("id")
        artist_name = normalise_text(song.get("artist-credit-phrase"))
        title = normalise_text(song.get("title"))
        antidupe_title = normalise_title_for_dupes(song.get("title"))
        song_key = (artist_name, antidupe_title)

        if not recording_id or recording_id in seen_recording_ids:
            continue

        if artist_name and title and song_key in seen_songs:
            continue

        try:
            song_data = format_musicbrainz_data(song)

            metadata_scores, relevance_score, _ = get_metadata_scores(
                song_data,
                artist,
                language,
                tags,
                title_keywords,
                similar_artists
            )

            song_data["score_breakdown"] = metadata_scores
            song_data["relevance_score"] = round(relevance_score, 3)

            recommendations.append(song_data)
            seen_recording_ids.add(recording_id)

            if artist_name and title:
                seen_songs.add(song_key)

        except Exception as e:
            print(f"Candidate {recording_id} skipped: {e}")

    return recommendations

def enrich_shortlist(shortlist):
    # only get detailed MusicBrainz data and Last.fm after shortlisting
    for song in shortlist:
        recording_id = song.get("mbid")

        try:
            full_song = get_full_recording(recording_id)
            full_song_data = format_musicbrainz_data(full_song)
            song.update(full_song_data)

        except Exception as e:
            print(f"Detailed MusicBrainz lookup skipped for {recording_id}: {e}")

    for song in shortlist:
        enrich_with_lastfm(song)

def calculate_final_scores(shortlist, artist, language, tags, title_keywords, similar_artists):
    # use highest shortlist values for normalising
    max_playcount = max((song.get("playcount") or 0 for song in shortlist), default=0)
    max_listeners = max((song.get("listeners") or 0 for song in shortlist), default=0)

    for song in shortlist:
        metadata_scores, relevance_score, metadata_match = get_metadata_scores(
            song,
            artist,
            language,
            tags,
            title_keywords,
            similar_artists
        )

        popularity_score = calculate_popularity_score(
            song.get("playcount"),
            song.get("listeners"),
            max_playcount,
            max_listeners
        )

        final_score = calculate_final_score(relevance_score, popularity_score)

        song["score_breakdown"] = metadata_scores
        song["relevance_score"] = round(relevance_score, 3)
        song["popularity_score"] = round(popularity_score, 3)
        song["final_score"] = round(final_score, 3)
        song["metadata_match"] = metadata_match
        song["is_related_artist"] = any(
            normalise_text(song.get("artist")) == normalise_text(item.get("name"))
            for item in similar_artists
        )

@api_view(["GET"])
def search_song(request):
    artist = request.GET.get("artist", "").strip()
    language = request.GET.get("language", "").strip()
    tags = request.GET.get("tags", "").strip()
    title_keywords = request.GET.get("title_keywords", "").strip()
    include_similar_artists = (request.GET.get("include_similar_artists","false").lower() == "true")

    language_list = [lang.strip() for lang in language.split(",") if lang.strip()]

    # At least one searchable field must be provided
    if not any([artist, tags, language, title_keywords]):
        return Response(
            {
                "error": (
                    "Enter at least one artist, language, genre/tag, or title keyword"
                )
            },
            status=400
        )

    try:
        # build search query and get similar artists if requested
        shortlist_limit = 20
        candidate_limit = 50

        match_parts, similar_artists, candidate_artists = build_search_queries(
            artist, tags, title_keywords, include_similar_artists
        )

        recordings = search_musicbrainz_candidates(
            artist, candidate_artists, match_parts, candidate_limit
        )

        if language:
            recordings.extend(
                search_language_candidates(
                    language_list, artist, candidate_artists, shortlist_limit
                )
            )

        if not recordings:
            return Response(
                {"error": "No songs found"},
                status=404
            )

        recommendations = score_candidates(
            recordings, artist, language, tags, title_keywords, similar_artists
        )

        if not recommendations:
            return Response(
                {"error": "No usable songs found"},
                status=404
            )

        recommendations.sort(
            key=lambda song: song["relevance_score"],
            reverse=True
        )

        # Keep the best 20 for later enrichment
        shortlist = select_diverse_shortlist(
            recommendations,
            limit=shortlist_limit,
            max_per_artist=5
        )

        # Get detailed musicbrainz metadata for the top 20
        enrich_shortlist(shortlist)

        calculate_final_scores(
            shortlist, artist, language, tags, title_keywords, similar_artists
        )
        
        shortlist.sort(
            key=lambda song: song["final_score"],
            reverse=True
        )

        if not shortlist:
            error_message = (
                "No songs matched the requested language and preferences"
                if language
                else "No suitable songs found"
            )

            return Response({"error": error_message}, status=404
            )

        if include_similar_artists:
            top_recommendations = rerank_for_diversity(
                shortlist,
                limit=shortlist_limit,
                max_per_artist=2
            )
        else:
            top_recommendations = shortlist[:shortlist_limit]
        
        return Response({
            "recommendations": top_recommendations
        })

    except Exception as e:
        print("Search song error:", e)

        return Response(
            {"error": str(e)},
            status=500
        )