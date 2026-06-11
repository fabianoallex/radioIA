"""Testa funções puras do plugin url.py.

_youtube_video_id(): detecta e extrai o ID de vídeos do YouTube.
fetch() com múltiplas URLs: verifica que URLs separadas por vírgula
geram múltiplos itens (usando mock do trafilatura).
"""

import pytest
from unittest.mock import MagicMock, patch
from plugins.url import _youtube_video_id, fetch


class TestYoutubeVideoId:
    def test_watch_url(self):
        assert _youtube_video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ') == 'dQw4w9WgXcQ'

    def test_short_url(self):
        assert _youtube_video_id('https://youtu.be/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'

    def test_shorts_url(self):
        assert _youtube_video_id('https://www.youtube.com/shorts/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'

    def test_watch_url_with_extra_params(self):
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s&list=PL123'
        assert _youtube_video_id(url) == 'dQw4w9WgXcQ'

    def test_non_youtube_returns_none(self):
        assert _youtube_video_id('https://vimeo.com/video/123456') is None

    def test_regular_article_returns_none(self):
        assert _youtube_video_id('https://g1.globo.com/tecnologia/noticia') is None

    def test_empty_string_returns_none(self):
        assert _youtube_video_id('') is None

    def test_youtube_domain_without_video_id_returns_none(self):
        # URL do YouTube sem parâmetro v= válido
        assert _youtube_video_id('https://www.youtube.com/channel/UCxxx') is None


class TestFetchMultipleUrls:
    """fetch() com múltiplas URLs separadas por vírgula deve retornar um item por URL."""

    def _make_meta(self, title='Título', sitename='Site', date='2026-06-11'):
        meta = MagicMock()
        meta.title    = title
        meta.sitename = sitename
        meta.date     = date
        return meta

    def test_single_url_returns_one_item(self, monkeypatch):
        monkeypatch.setattr('plugins.url.trafilatura.fetch_url', lambda url: 'html')
        monkeypatch.setattr('plugins.url.trafilatura.extract', lambda *a, **kw: 'Conteúdo.')
        monkeypatch.setattr('plugins.url.trafilatura.extract_metadata',
                            lambda html: self._make_meta())

        items = fetch({'settings': {'url': 'https://exemplo.com'}})
        assert len(items) == 1
        assert items[0]['url'] == 'https://exemplo.com'

    def test_multiple_urls_returns_one_item_per_url(self, monkeypatch):
        monkeypatch.setattr('plugins.url.trafilatura.fetch_url', lambda url: 'html')
        monkeypatch.setattr('plugins.url.trafilatura.extract', lambda *a, **kw: 'Conteúdo.')
        monkeypatch.setattr('plugins.url.trafilatura.extract_metadata',
                            lambda html: self._make_meta())

        items = fetch({'settings': {'url': 'https://a.com,https://b.com,https://c.com'}})
        assert len(items) == 3
        urls = [i['url'] for i in items]
        assert 'https://a.com' in urls
        assert 'https://b.com' in urls
        assert 'https://c.com' in urls

    def test_url_with_no_content_skipped(self, monkeypatch):
        monkeypatch.setattr('plugins.url.trafilatura.fetch_url', lambda url: None)

        items = fetch({'settings': {'url': 'https://inacessivel.com'}})
        assert items == []

    def test_item_contains_required_fields(self, monkeypatch):
        monkeypatch.setattr('plugins.url.trafilatura.fetch_url', lambda url: 'html')
        monkeypatch.setattr('plugins.url.trafilatura.extract', lambda *a, **kw: 'Texto do artigo.')
        monkeypatch.setattr('plugins.url.trafilatura.extract_metadata',
                            lambda html: self._make_meta('Meu Título', 'G1', '2026-06-10'))

        items = fetch({'settings': {'url': 'https://g1.com/artigo'}})
        assert len(items) == 1
        item = items[0]
        assert item['title']        == 'Meu Título'
        assert item['source_name']  == 'G1'
        assert item['published_at'] == '2026-06-10'
        assert item['text']         == 'Texto do artigo.'
        assert item['source_type']  == 'url'
        assert 'id' in item

    def test_partial_failure_skips_bad_url(self, monkeypatch):
        """URL que não retorna conteúdo é ignorada; as demais são processadas."""
        def fake_fetch(url):
            return None if 'bad' in url else 'html'

        monkeypatch.setattr('plugins.url.trafilatura.fetch_url', fake_fetch)
        monkeypatch.setattr('plugins.url.trafilatura.extract', lambda *a, **kw: 'Conteúdo.')
        monkeypatch.setattr('plugins.url.trafilatura.extract_metadata',
                            lambda html: self._make_meta())

        items = fetch({'settings': {'url': 'https://good.com,https://bad.com'}})
        assert len(items) == 1
        assert items[0]['url'] == 'https://good.com'
