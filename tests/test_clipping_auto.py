import json
import os
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

import plugins.clipping_auto as ca


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_history(entries: list[dict], tmp_path: str) -> str:
    path = os.path.join(tmp_path, '_clipping_auto_history.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f)
    return path


# ── _is_similar ───────────────────────────────────────────────────────────────

class TestIsSimilar:
    def test_identical_topics_similar(self):
        assert ca._is_similar('reforma tributária', ['reforma tributária']) is True

    def test_overlapping_keywords_similar(self):
        assert ca._is_similar('greve dos professores', ['professores fazem greve']) is True

    def test_unrelated_topics_not_similar(self):
        assert ca._is_similar('copa do mundo', ['eleições presidenciais']) is False

    def test_empty_recent_not_similar(self):
        assert ca._is_similar('qualquer coisa', []) is False

    def test_stopwords_ignored(self):
        # "de" e "da" são stopwords; sem palavras reais em comum
        assert ca._is_similar('de da do', ['em no na']) is False

    def test_threshold_boundary(self):
        # Jaccard = 1/3 ≈ 0.33 < 0.4 → não similar
        assert ca._is_similar('a b c', ['a d e']) is False

    def test_matches_any_in_list(self):
        # Jaccard({'futebol','copa','brasil'} ∩ {'futebol','copa','mundo'}) = 2/4 = 0.5 ≥ 0.4
        recent = ['futebol copa brasil', 'eleições gerais']
        assert ca._is_similar('futebol copa mundo', recent) is True


# ── _load_recent_topics ───────────────────────────────────────────────────────

class TestLoadRecentTopics:
    def test_returns_empty_when_no_file(self, tmp_path):
        with patch.object(ca, 'HISTORY_PATH', str(tmp_path / 'nonexistent.json')):
            assert ca._load_recent_topics(7) == []

    def test_returns_topics_within_window(self, tmp_path):
        today = date.today().isoformat()
        entries = [
            {'topic': 'reforma tributária', 'date': today, 'datetime': datetime.now().isoformat(), 'categoria': ''},
        ]
        path = _make_history(entries, str(tmp_path))
        with patch.object(ca, 'HISTORY_PATH', path):
            topics = ca._load_recent_topics(7)
        assert 'reforma tributária' in topics

    def test_excludes_topics_outside_window(self, tmp_path):
        old_date = (date.today() - timedelta(days=10)).isoformat()
        entries = [
            {'topic': 'notícia antiga', 'date': old_date, 'datetime': datetime.now().isoformat(), 'categoria': ''},
        ]
        path = _make_history(entries, str(tmp_path))
        with patch.object(ca, 'HISTORY_PATH', path):
            topics = ca._load_recent_topics(7)
        assert 'notícia antiga' not in topics

    def test_cooldown_includes_recent_hours(self, tmp_path):
        old_date = (date.today() - timedelta(days=10)).isoformat()
        recent_dt = (datetime.now() - timedelta(hours=2)).isoformat()
        entries = [
            {'topic': 'assunto recente', 'date': old_date, 'datetime': recent_dt, 'categoria': ''},
        ]
        path = _make_history(entries, str(tmp_path))
        with patch.object(ca, 'HISTORY_PATH', path):
            topics = ca._load_recent_topics(7, cooldown_hours=4)
        assert 'assunto recente' in topics

    def test_cooldown_excludes_old_hours(self, tmp_path):
        old_date = (date.today() - timedelta(days=10)).isoformat()
        old_dt = (datetime.now() - timedelta(hours=6)).isoformat()
        entries = [
            {'topic': 'assunto antigo', 'date': old_date, 'datetime': old_dt, 'categoria': ''},
        ]
        path = _make_history(entries, str(tmp_path))
        with patch.object(ca, 'HISTORY_PATH', path):
            topics = ca._load_recent_topics(7, cooldown_hours=4)
        assert 'assunto antigo' not in topics


# ── _load_today_topics ────────────────────────────────────────────────────────

class TestLoadTodayTopics:
    def test_returns_only_todays_topics(self, tmp_path):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        entries = [
            {'topic': 'hoje', 'date': today, 'datetime': datetime.now().isoformat(), 'categoria': ''},
            {'topic': 'ontem', 'date': yesterday, 'datetime': datetime.now().isoformat(), 'categoria': ''},
        ]
        path = _make_history(entries, str(tmp_path))
        with patch.object(ca, 'HISTORY_PATH', path):
            topics = ca._load_today_topics()
        assert topics == ['hoje']

    def test_returns_empty_when_no_file(self, tmp_path):
        with patch.object(ca, 'HISTORY_PATH', str(tmp_path / 'none.json')):
            assert ca._load_today_topics() == []


# ── _save_topic ───────────────────────────────────────────────────────────────

class TestSaveTopic:
    def test_saves_entry(self, tmp_path):
        path = str(tmp_path / 'history.json')
        with patch.object(ca, 'HISTORY_PATH', path):
            ca._save_topic('novo assunto', 'economia')
        with open(path, 'r', encoding='utf-8') as f:
            history = json.load(f)
        assert len(history) == 1
        assert history[0]['topic'] == 'novo assunto'
        assert history[0]['categoria'] == 'economia'
        assert history[0]['date'] == date.today().isoformat()

    def test_accumulates_entries(self, tmp_path):
        path = str(tmp_path / 'history.json')
        with patch.object(ca, 'HISTORY_PATH', path):
            ca._save_topic('primeiro', '')
            ca._save_topic('segundo', '')
        with open(path, 'r', encoding='utf-8') as f:
            history = json.load(f)
        assert len(history) == 2

    def test_prunes_old_entries(self, tmp_path):
        very_old = (date.today() - timedelta(days=ca.HISTORY_KEEP_DAYS + 1)).isoformat()
        old_entries = [
            {'topic': 'velho', 'date': very_old, 'datetime': datetime.now().isoformat(), 'categoria': ''},
        ]
        path = _make_history(old_entries, str(tmp_path))
        with patch.object(ca, 'HISTORY_PATH', path):
            ca._save_topic('novo', '')
        with open(path, 'r', encoding='utf-8') as f:
            history = json.load(f)
        topics = [e['topic'] for e in history]
        assert 'velho' not in topics
        assert 'novo' in topics


# ── _collect_headlines ────────────────────────────────────────────────────────

class TestCollectHeadlines:
    def test_collects_titles_from_feed(self):
        fake_entry = type('E', (), {'get': lambda self, k, d='': 'Título de teste' if k == 'title' else d})()
        fake_feed  = type('F', (), {'entries': [fake_entry]})()
        with patch('feedparser.parse', return_value=fake_feed):
            results = ca._collect_headlines(['http://fake/rss'], date.today())
        assert 'Título de teste' in results

    def test_deduplicates_titles(self):
        fake_entry = type('E', (), {'get': lambda self, k, d='': 'Duplicado' if k == 'title' else d})()
        fake_feed  = type('F', (), {'entries': [fake_entry, fake_entry]})()
        with patch('feedparser.parse', return_value=fake_feed):
            results = ca._collect_headlines(['http://fake/rss'], date.today())
        assert results.count('Duplicado') == 1

    def test_skips_empty_title(self):
        fake_entry = type('E', (), {'get': lambda self, k, d='': '' if k == 'title' else d})()
        fake_feed  = type('F', (), {'entries': [fake_entry]})()
        with patch('feedparser.parse', return_value=fake_feed):
            results = ca._collect_headlines(['http://fake/rss'], date.today())
        assert results == []

    def test_feed_error_does_not_crash(self):
        with patch('feedparser.parse', side_effect=Exception('timeout')):
            results = ca._collect_headlines(['http://fake/rss'], date.today())
        assert results == []
