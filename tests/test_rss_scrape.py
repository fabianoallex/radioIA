"""Testa o path scrape: true do rss.py.

Cobre: fetch() com scrape, _scrape_page_links() e _extract_article().
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.sources.rss import _extract_article, _scrape_page_links, fetch


class TestFetchScrape:
    """fetch() com feed_config contendo scrape: true."""

    # HTML mínimo sem link RSS — garante que auto-descoberta de RSS retorne None
    _HTML_VAZIO = '<html><head></head><body></body></html>'

    def _config(self, max_per_feed=3, max_total=10, days_lookback=1):
        return {
            'feeds': [{'url': 'https://portal.com/', 'name': 'Portal', 'scrape': True}],
            'settings': {
                'max_items_per_feed': max_per_feed,
                'max_items_total': max_total,
                'days_lookback': days_lookback,
            },
        }

    def _mock_base(self, monkeypatch):
        """Mocks comuns: _fetch_html retorna HTML sem RSS; _scrape_page_links e _extract_article livres."""
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: self._HTML_VAZIO)

    def test_itens_coletados(self, monkeypatch):
        self._mock_base(monkeypatch)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: ['https://portal.com/art1'])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', 'Texto.', None))

        items = fetch(self._config())
        assert len(items) == 1
        assert items[0]['title'] == 'Título'
        assert items[0]['url'] == 'https://portal.com/art1'
        assert items[0]['source_name'] == 'Portal'

    def test_item_sem_titulo_descartado(self, monkeypatch):
        self._mock_base(monkeypatch)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: ['https://portal.com/art1'])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('', 'Texto.', None))

        assert fetch(self._config()) == []

    def test_item_sem_texto_descartado(self, monkeypatch):
        self._mock_base(monkeypatch)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: ['https://portal.com/art1'])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', '', None))

        assert fetch(self._config()) == []

    def test_max_items_per_feed_respeitado(self, monkeypatch):
        self._mock_base(monkeypatch)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: [f'https://portal.com/art{i}' for i in range(10)])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', 'Texto.', None))

        assert len(fetch(self._config(max_per_feed=2))) == 2

    def test_todos_feeds_consultados_independente_de_max_total(self, monkeypatch):
        # fetch() agora retorna candidatos de TODOS os feeds sem early-stop por max_total.
        # O cap é aplicado pelo caller (_run_source) após filtrar seen_ids.
        self._mock_base(monkeypatch)
        config = {
            'feeds': [
                {'url': 'https://a.com/', 'name': 'A', 'scrape': True},
                {'url': 'https://b.com/', 'name': 'B', 'scrape': True},
            ],
            'settings': {'max_items_per_feed': 5, 'max_items_total': 3, 'days_lookback': 1},
        }
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: [f'{url}art{i}' for i in range(5)])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', 'Texto.', None))

        # 2 feeds × max_per_feed=5 → 10 candidatos retornados (max_total ignorado aqui)
        assert len(fetch(config)) == 10

    def test_item_com_data_antiga_filtrado(self, monkeypatch):
        self._mock_base(monkeypatch)
        data_antiga = datetime.now(timezone.utc) - timedelta(days=3)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: ['https://portal.com/art1'])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', 'Texto.', data_antiga))

        assert fetch(self._config(days_lookback=1)) == []

    def test_item_sem_data_nao_filtrado(self, monkeypatch):
        """Sem data disponível o item é incluído — página inicial pressupõe conteúdo recente."""
        self._mock_base(monkeypatch)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: ['https://portal.com/art1'])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', 'Texto.', None))

        assert len(fetch(self._config(days_lookback=1))) == 1

    def test_campos_obrigatorios_presentes(self, monkeypatch):
        self._mock_base(monkeypatch)
        monkeypatch.setattr('src.sources.rss._scrape_page_links',
                            lambda url: ['https://portal.com/art1'])
        monkeypatch.setattr('src.sources.rss._extract_article',
                            lambda url: ('Título', 'Texto.', None))

        item = fetch(self._config())[0]
        for campo in ('id', 'title', 'url', 'text', 'source_name', 'source_type', 'published_at'):
            assert campo in item

    def test_rss_autodescoberto_usado_quando_disponivel(self, monkeypatch):
        """Se a página declara RSS no <head>, usa feedparser em vez de scraping."""
        html_com_rss = (
            '<html><head>'
            '<link rel="alternate" type="application/rss+xml" href="/feed.xml"/>'
            '</head></html>'
        )
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: html_com_rss)
        monkeypatch.setattr('src.sources.rss._items_from_rss_url',
                            lambda rss_url, name, mpf, cutoff: [
                                {'id': 'x', 'title': 'Via RSS', 'url': 'x', 'text': 'T',
                                 'source_name': name, 'source_type': 'news',
                                 'published_at': '', 'views': 0, 'comments': [], 'channel': name}
                            ])

        items = fetch(self._config())
        assert len(items) == 1
        assert items[0]['title'] == 'Via RSS'


class TestScrapePageLinks:
    """_scrape_page_links(): filtragem e deduplicação de links."""

    _HTML = """
    <html><body>
      <a href="https://portal.com/noticia-1">N1</a>
      <a href="https://portal.com/noticia-2">N2</a>
      <a href="https://portal.com/noticia-1">N1 duplicada</a>
      <a href="https://externo.com/outro">Externo</a>
      <a href="/">Home</a>
      <a href="">Vazio</a>
    </body></html>
    """

    def test_links_internos_retornados(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: self._HTML)
        links = _scrape_page_links('https://portal.com/')
        assert 'https://portal.com/noticia-1' in links
        assert 'https://portal.com/noticia-2' in links

    def test_links_externos_filtrados(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: self._HTML)
        links = _scrape_page_links('https://portal.com/')
        assert not any('externo.com' in l for l in links)

    def test_path_raiz_filtrado(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: self._HTML)
        links = _scrape_page_links('https://portal.com/')
        assert 'https://portal.com/' not in links

    def test_duplicatas_removidas(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: self._HTML)
        links = _scrape_page_links('https://portal.com/')
        assert links.count('https://portal.com/noticia-1') == 1

    def test_retorna_lista_vazia_quando_fetch_falha(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: None)
        assert _scrape_page_links('https://portal.com/') == []

    def test_limita_candidatos(self, monkeypatch):
        """Retorna no máximo MAX_SCRAPE_CANDIDATES links."""
        from src.sources.rss import MAX_SCRAPE_CANDIDATES
        muitos_links = ''.join(
            f'<a href="https://portal.com/art{i}">Art {i}</a>' for i in range(100)
        )
        monkeypatch.setattr('src.sources.rss._fetch_html',
                            lambda url: f'<html><body>{muitos_links}</body></html>')
        links = _scrape_page_links('https://portal.com/')
        assert len(links) <= MAX_SCRAPE_CANDIDATES


class TestExtractArticle:
    """_extract_article(): parsing de JSON do trafilatura e falhas de rede."""

    def test_retorna_vazio_quando_fetch_falha(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: None)
        title, text, date = _extract_article('https://portal.com/art1')
        assert title == ''
        assert text == ''
        assert date is None

    def test_retorna_vazio_quando_extract_retorna_none(self, monkeypatch):
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: '<html/>')
        monkeypatch.setattr('src.sources.rss.trafilatura.extract', lambda *a, **kw: None)
        title, text, date = _extract_article('https://portal.com/art1')
        assert title == ''
        assert text == ''
        assert date is None

    def test_extrai_titulo_e_texto(self, monkeypatch):
        payload = json.dumps({'title': 'Meu Artigo', 'text': 'Conteúdo aqui.', 'date': None})
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: '<html/>')
        monkeypatch.setattr('src.sources.rss.trafilatura.extract', lambda *a, **kw: payload)
        title, text, date = _extract_article('https://portal.com/art1')
        assert title == 'Meu Artigo'
        assert text == 'Conteúdo aqui.'
        assert date is None

    def test_extrai_data_iso(self, monkeypatch):
        payload = json.dumps({'title': 'Art', 'text': 'Texto.', 'date': '2026-06-14'})
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: '<html/>')
        monkeypatch.setattr('src.sources.rss.trafilatura.extract', lambda *a, **kw: payload)
        _, _, date = _extract_article('https://portal.com/art1')
        assert date is not None
        assert date.year == 2026
        assert date.month == 6
        assert date.day == 14

    def test_data_invalida_retorna_none(self, monkeypatch):
        payload = json.dumps({'title': 'Art', 'text': 'Texto.', 'date': 'nao-e-data'})
        monkeypatch.setattr('src.sources.rss._fetch_html', lambda url: '<html/>')
        monkeypatch.setattr('src.sources.rss.trafilatura.extract', lambda *a, **kw: payload)
        _, _, date = _extract_article('https://portal.com/art1')
        assert date is None
