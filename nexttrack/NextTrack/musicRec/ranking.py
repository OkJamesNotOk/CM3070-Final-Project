import math
import re

LANGUAGE_CODES = {
    "english": "eng",
    "japanese": "jpn",
    "korean": "kor",
    "chinese": "zho",
    "spanish": "spa",
    "french": "fra",
    "german": "deu",
    "italian": "ita",
    "portuguese": "por",
}

def normalise_text(value):
    if not value:
        return ""

    return value.strip().lower()

def normalise_title_for_dupes(title):
    title = normalise_text(title)

    # Remove trailing descriptions with brackets
    title = re.sub(r'\s*[\(\[\{][^)\]\}]*[\)\]\}]\s*$', '', title)

    # remove trailing descriptions with - sumthign -
    title = re.sub(r'\s*-\s*[^-]+?\s*-\s*$', '', title)

    # Ignore punctuation and spacing
    title = re.sub(r'[^\w]+', '', title)

    return title

def normalise_tags(tags):
    if not tags:
        return set()

    return {
        normalise_text(tag)
        for tag in tags
        if tag
    }

def get_requested_tags(tags):
    if not tags:
        return set()
    
    return normalise_tags(
        tag.strip()
        for tag in tags.split(",")
        if tag.strip()
    )

def calculate_tag_score(requested_tags, candidate_tags):
    requested_tags = normalise_tags(requested_tags)
    candidate_tags = normalise_tags(candidate_tags)

    if not requested_tags:
        return None

    if not candidate_tags:
        return 0.0

    matches = requested_tags.intersection(candidate_tags)

    return len(matches) / len(requested_tags)

def calculate_artist_score(requested_artist, candidate_artist, similar_artists=None):
    if not requested_artist:
        return None

    if not candidate_artist:
        return 0.0

    requested = normalise_text(requested_artist)
    candidate = normalise_text(candidate_artist)

    if requested == candidate:
        return 1.0

    for similar in similar_artists or []:
        similar_name = normalise_text(
            similar.get("name")
        )

        # slight reduce score for similar artists
        if candidate == similar_name:
            return 0.8 * float(similar.get("match", 0))

    if requested in candidate or candidate in requested:
        return 0.5

    return 0.0

def calculate_language_score(requested_language, candidate_language, candidate_tags):
    if not requested_language:
        return None

    requested_languages = {
        normalise_text(lang)
        for lang in requested_language.split(",")
        if lang.strip()
    }
    requested_codes = {
        LANGUAGE_CODES.get(lang, lang)
        for lang in requested_languages
    }

    candidate_language = normalise_text(candidate_language)

    # Prefer musicbrainz language information when available
    if candidate_language:
        return 1.0 if candidate_language in requested_codes else 0.0

    # Fall back to tags only when musicbrainz language is missing
    candidate_tags = normalise_tags(candidate_tags)
    return 1.0 if requested_languages.intersection(candidate_tags) else 0.0

def calculate_keyword_score(title_keywords, candidate_title):
    if not title_keywords:
        return None

    if not candidate_title:
        return 0.0

    requested_words = set(normalise_text(title_keywords).split())

    candidate_words = set(normalise_text(candidate_title).split())

    if not requested_words:
        return None

    matches = requested_words.intersection(candidate_words)

    return len(matches) / len(requested_words)

def calculate_metadata_scores(
    song, artist, language, tags, title_keywords, similar_artists=None
):
    requested_tags = get_requested_tags(tags)

    return {
        "tag_score": calculate_tag_score(
            requested_tags,
            song.get("combined_tags", [])
        ),

        "artist_score": calculate_artist_score(artist, song.get("artist"), similar_artists),

        "language_score": calculate_language_score(
            language,
            song.get("language"),
            song.get("combined_tags", [])
        ),

        "keyword_score": calculate_keyword_score(
            title_keywords,
            song.get("title")
        )
    }

# weight for each search preference when calculating relevance
METADATA_WEIGHT = {
    "tag_score": 0.30,
    "artist_score": 0.30,
    "language_score": 0.10,
    "keyword_score": 0.20,
}

def calculate_relevance_score(scores):
    active = {
        key: value
        for key, value in scores.items()
        if value is not None
    }

    if not active:
        return 0.0

    total_weight = sum(METADATA_WEIGHT[key] for key in active)

    score = sum(active[key] * METADATA_WEIGHT[key] for key in active)

    return score / total_weight

def normalise_popularity(value, max_value):
    if not value or not max_value:
        return 0.0

    return (math.log1p(value) / math.log1p(max_value))

def calculate_popularity_score(playcount, listeners, max_playcount, max_listeners):
    playcount_score = normalise_popularity(playcount, max_playcount)

    listener_score = normalise_popularity(listeners, max_listeners)

    return (0.8 * playcount_score + 0.2 * listener_score)

# user preference is main factor, popularity is small supporting factor
def calculate_final_score(relevance_score, popularity_score):
    return (0.90 * relevance_score + 0.10 * popularity_score)

def select_diverse_shortlist(recommendations, limit=20, max_per_artist=4
):
    selected = []
    skipped = []
    artist_counts = {}

    for song in recommendations:
        artist = normalise_text(song.get("artist"))

        count = artist_counts.get(artist, 0)

        if count < max_per_artist:
            selected.append(song)

            artist_counts[artist] = (count + 1)
        else:
            skipped.append(song)

        if len(selected) >= limit:
            return selected

    # fill up the rest if not enough different artists
    for song in skipped:
        if len(selected) >= limit:
            break

        selected.append(song)

    return selected

def rerank_for_diversity(ranked_songs, limit=5, max_per_artist=2):
    selected = []
    skipped = []
    artist_counts = {}

    for song in ranked_songs:
        artist = normalise_text(song.get("artist"))

        count = artist_counts.get(artist, 0)

        if count < max_per_artist:
            selected.append(song)

            artist_counts[artist] = (count + 1)
        else:
            skipped.append(song)

        if len(selected) >= limit:
            return selected

    # Fallback if not enough different artists
    for song in skipped:
        if len(selected) >= limit:
            break

        selected.append(song)

    return selected