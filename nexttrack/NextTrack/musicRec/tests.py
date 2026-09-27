from django.test import TestCase
from unittest.mock import Mock, patch
from rest_framework.test import APIRequestFactory
from . import apiCalls, views
from .apiCalls import format_length, format_musicbrainz_data
from .ranking import (
    normalise_text, normalise_title_for_dupes, calculate_tag_score,
    calculate_artist_score, calculate_language_score, calculate_keyword_score,
    calculate_relevance_score, calculate_popularity_score, calculate_final_score,
    select_diverse_shortlist, rerank_for_diversity
)

class ApiCallsTests(TestCase):
    def test_format_length(self):
        self.assertEqual(format_length(125000), "2:05")
        self.assertEqual(format_length(185000), "3:05")

    def test_format_length_none(self):
        self.assertIsNone(format_length(None))

    def test_format_musicbrainz_data(self):
        song = {
            "id": "mili101",
            "title": "Birthday Kid",
            "artist-credit-phrase": "Mili",
            "length": 185000,
            "release-list": [{"title": "Miracle Milk"}],
            "work-relation-list": [{"work": {"language": "eng"}}],
            "tag-list": [{"name": "japanese"}, {"name": "j-pop"}],
            "url-relation-list": [{"type": "youtube", "target": "https://youtube.com/test"}]
        }
        result = format_musicbrainz_data(song)
        self.assertEqual(result["title"], "Birthday Kid")
        self.assertEqual(result["artist"], "Mili")
        self.assertEqual(result["length"], "3:05")
        self.assertEqual(result["release"], "Miracle Milk")
        self.assertEqual(result["language"], "eng")
        self.assertEqual(result["combined_tags"], ["japanese", "j-pop"])

    @patch(f"{apiCalls.__name__}.requests.get")
    def test_lastfm_data(self, mock_get):
        # Mock successful Last.fm response
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "track": {
                "listeners": "67",
                "playcount": "69420",
                "url": "https://last.fm/test",
                "toptags": {"tag": [
                    {"name": "japanese"}, 
                    {"name": "j-pop"},
                    {"name": "pop"}, 
                    {"name": "electronic"},
                    {"name": "alternative"}
                ]}
            }
        }
        mock_get.return_value = response
        result = apiCalls.get_lastfm_data("Mili", "Birthday Kid")
        self.assertEqual(result["listeners"], 67)
        self.assertEqual(result["playcount"], 69420)
        self.assertEqual(len(result["tags"]), 5)
        self.assertEqual(result["lastfm_url"], "https://last.fm/test")

    def test_lastfm_failure(self):
        # Simulate Last.fm being unavailable
        with patch(f"{apiCalls.__name__}.requests.get", side_effect=Exception("API unavailable")):
            result = apiCalls.get_lastfm_data("Mili", "Birthday Kid")
        self.assertIsNone(result["listeners"])
        self.assertIsNone(result["playcount"])
        self.assertEqual(result["tags"], [])
        self.assertIsNone(result["lastfm_url"])

class RankingTests(TestCase):
    def test_text_normalisation(self):
        self.assertEqual(normalise_text("  Mili  "), "mili")
        self.assertEqual(normalise_text(None), "")
        self.assertEqual(normalise_title_for_dupes("Birthday Kid (Key Ingredient Ver.)"), "birthdaykid")
        self.assertEqual(normalise_title_for_dupes("Birthday Kid"), "birthdaykid")

    def test_tag_scores(self):
        self.assertEqual(calculate_tag_score({"j-pop", "electronic"}, {"j-pop", "pop"}), 0.5)
        self.assertEqual(calculate_tag_score({"electronic"}, []), 0.0)
        self.assertIsNone(calculate_tag_score([], {"pop"}))

    def test_artist_scores(self):
        self.assertEqual(calculate_artist_score("Mili", "Mili"), 1.0)
        self.assertEqual(calculate_artist_score("Mili", "mili mili"), 0.5)

        # Similar artists receive 80% of their match value
        similar = [{"name": "Ado", "match": 0.75}]
        self.assertAlmostEqual(calculate_artist_score("Mili", "Ado", similar), 0.6)

    def test_language_scores(self):
        self.assertEqual(calculate_language_score("Japanese", "jpn", []), 1.0)
        self.assertEqual(calculate_language_score("Japanese", None, ["japanese", "electronic"]), 1.0)
        self.assertEqual(calculate_language_score("Japanese", "eng", ["japanese"]), 0.0)

    def test_keyword_score(self):
        self.assertEqual(calculate_keyword_score("key ingredient", "Key Ingredient Version"), 1.0)
        self.assertEqual(calculate_keyword_score("key ingredient", "Key Song"), 0.5)

    def test_relevance_score(self):
        # Missing criteria should not contribute score
        scores = {
            "tag_score": 1.0,
            "artist_score": 0.0,
            "language_score": None,
            "keyword_score": 0.5
        }
        self.assertAlmostEqual(calculate_relevance_score(scores), 0.5)
        # No active criteria should return a relevance score of zero
        empty_scores = {
            "tag_score": None,
            "artist_score": None,
            "language_score": None,
            "keyword_score": None
        }
        self.assertEqual(calculate_relevance_score(empty_scores), 0.0)

    def test_popularity_and_final_score(self):
        popularity = calculate_popularity_score(1000, 500, 1000, 500)
        self.assertEqual(popularity, 1.0)
        self.assertAlmostEqual(calculate_final_score(0.8, 0.5), 0.77)

    songs = [
        {"title": "Birthday Kid", "artist": "Mili"},
        {"title": "String Theocracy", "artist": "Mili"},
        {"title": "Ga1ahad and Scientific Witchery", "artist": "Mili"},
        {"title": "Usseewa", "artist": "Ado"},
        {"title": "shadowgraph", "artist": "MYTH & ROID"}
    ]
    def test_diverse_shortlist(self):
        # check that per artist limit is applied
        result = select_diverse_shortlist(self.songs, limit=4, max_per_artist=2)
        self.assertEqual([song["title"] for song in result], ["Birthday Kid", "String Theocracy", "Usseewa", "shadowgraph"])

    def test_final_diversity(self):
        # Limit each artist to one
        result = rerank_for_diversity(self.songs, limit=3, max_per_artist=1)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["title"], "Birthday Kid")
        self.assertEqual(result[1]["title"], "Usseewa")

class SearchSongTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_empty_search(self):
        request = self.factory.get("/api/search/")
        response = views.search_song(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    def test_no_results(self):
        # mock no results
        with patch(f"{views.__name__}.search_musicbrainz_candidates", return_value=[]):
            request = self.factory.get("/api/search/", {"artist": "Mili"})
            response = views.search_song(request)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "No songs found")

    @patch(f"{views.__name__}.search_musicbrainz_candidates")
    @patch(f"{views.__name__}.score_candidates")
    @patch(f"{views.__name__}.enrich_shortlist")
    def test_successful_search(self, mock_enrich, mock_score, mock_search):
        # mock candidate without calling MusicBrainz
        mock_search.return_value = [{
            "id": "mili101",
            "title": "Birthday Kid",
            "artist-credit-phrase": "Mili"
        }]
        mock_score.return_value = [{
            "mbid": "mili101",
            "title": "Birthday Kid",
            "artist": "Mili",
            # initial score before final ranking
            "relevance_score": 1.0,
        }]

        request = self.factory.get("/api/search/", {"artist": "Mili"})
        response = views.search_song(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["recommendations"]), 1)
        self.assertEqual(response.data["recommendations"][0]["title"], "Birthday Kid")
        self.assertEqual(response.data["recommendations"][0]["final_score"], 0.9)

    def test_search_req_error(self):
        # Simulate a failed search 
        with patch(f"{views.__name__}.search_musicbrainz_candidates", side_effect=RuntimeError("MusicBrainz unavailable")):
            request = self.factory.get("/api/search/", {"artist": "Mili"})
            response = views.search_song(request)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"], "MusicBrainz unavailable")