"""Testa _parse_fonte() do mcp_tools._utils.

A função mapeia strings de fonte para (source_id, param, context),
suportando o formato  source_id[:param][|contexto].
"""

import pytest

utils = pytest.importorskip(
    'mcp_tools._utils',
    reason='mcp_tools._utils não importável (dependências ausentes)',
)
_parse_fonte = utils._parse_fonte


class TestParseFonte:
    def test_simple_source(self):
        assert _parse_fonte('youtube') == ('youtube', None, '')

    def test_source_with_param(self):
        assert _parse_fonte('musica:3') == ('musica', '3', '')

    def test_source_with_context(self):
        assert _parse_fonte('noticias|foca em economia') == ('noticias', None, 'foca em economia')

    def test_source_with_param_and_context(self):
        assert _parse_fonte('musica:3|prefira MPB') == ('musica', '3', 'prefira MPB')

    def test_url_simple(self):
        sid, param, ctx = _parse_fonte('url:https://exemplo.com/artigo')
        assert sid   == 'url'
        assert param == 'https://exemplo.com/artigo'
        assert ctx   == ''

    def test_url_with_context(self):
        sid, param, ctx = _parse_fonte('url:https://exemplo.com|extraia pontos técnicos')
        assert sid   == 'url'
        assert param == 'https://exemplo.com'
        assert ctx   == 'extraia pontos técnicos'

    def test_url_multi_without_context(self):
        sid, param, ctx = _parse_fonte('url:https://a.com,https://b.com')
        assert sid   == 'url'
        assert param == 'https://a.com,https://b.com'
        assert ctx   == ''

    def test_url_multi_with_context(self):
        sid, param, ctx = _parse_fonte('url:https://a.com,https://b.com|compare as abordagens')
        assert sid   == 'url'
        assert param == 'https://a.com,https://b.com'
        assert ctx   == 'compare as abordagens'

    def test_context_with_pipe_in_value(self):
        # Apenas o PRIMEIRO | separa — resto é parte do contexto
        sid, param, ctx = _parse_fonte('noticias|foco: economia | política')
        assert sid == 'noticias'
        assert ctx == 'foco: economia | política'

    def test_whitespace_stripped(self):
        sid, param, ctx = _parse_fonte('  noticias  |  foco em tech  ')
        assert sid == 'noticias'
        assert ctx == 'foco em tech'

    def test_clipping_with_param(self):
        sid, param, ctx = _parse_fonte('clipping:reforma tributária')
        assert sid   == 'clipping'
        assert param == 'reforma tributária'
        assert ctx   == ''
