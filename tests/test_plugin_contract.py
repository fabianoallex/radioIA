"""
Testes de contrato para plugins RadioIA.

Todo plugin deve implementar:
    fetch(source_config: dict, credentials=None) -> list[dict]

Cada item retornado deve ter os campos de REQUIRED_FIELDS.
Campos opcionais em OPTIONAL_FIELDS são verificados apenas se presentes.

Para validar um novo plugin, use assert_valid_plugin_items():

    from tests.test_plugin_contract import assert_valid_plugin_items
    items = meu_plugin.fetch(source_config)
    assert_valid_plugin_items(items)
"""

import pytest
from unittest.mock import patch, MagicMock


REQUIRED_FIELDS = {
    'id':           str,
    'title':        str,
    'url':          str,
    'text':         str,
    'source_name':  str,
    'source_type':  str,
    'published_at': str,
}

OPTIONAL_FIELDS = {
    'views':    int,
    'comments': list,
    'channel':  str,
}


def assert_valid_plugin_items(items, allow_empty=False):
    """Valida que o retorno de fetch() respeita o contrato de plugin RadioIA."""
    assert isinstance(items, list), "fetch() deve retornar uma lista"
    if not allow_empty:
        assert len(items) > 0, "fetch() retornou lista vazia"
    for i, item in enumerate(items):
        assert isinstance(item, dict), f"Item {i} não é um dict"
        for field, expected_type in REQUIRED_FIELDS.items():
            assert field in item, f"Item {i}: campo obrigatório ausente: '{field}'"
            assert isinstance(item[field], expected_type), (
                f"Item {i}: '{field}' deve ser {expected_type.__name__}, "
                f"mas é {type(item[field]).__name__}"
            )
        assert item['id'],   f"Item {i}: 'id' não pode ser vazio"
        assert item['text'], f"Item {i}: 'text' não pode ser vazio"
        for field, expected_type in OPTIONAL_FIELDS.items():
            if field in item:
                assert isinstance(item[field], expected_type), (
                    f"Item {i}: campo opcional '{field}' deve ser {expected_type.__name__}"
                )


# ── Exemplo plugin (sem dependências externas) ────────────────────────────────

class TestExemploPlugin:
    BASE_CONFIG = {'name': 'Frase do Dia', 'type': 'exemplo_plugin'}

    def test_retorna_contrato_valido(self):
        from plugins.exemplo_plugin import fetch
        config = {**self.BASE_CONFIG, 'settings': {'categoria': 'motivacional'}}
        assert_valid_plugin_items(fetch(config))

    def test_todas_as_categorias(self):
        from plugins.exemplo_plugin import fetch
        for categoria in ('motivacional', 'filosofia', 'humor'):
            config = {**self.BASE_CONFIG, 'settings': {'categoria': categoria}}
            assert_valid_plugin_items(fetch(config))

    def test_config_sem_settings(self):
        from plugins.exemplo_plugin import fetch
        assert_valid_plugin_items(fetch(self.BASE_CONFIG))

    def test_source_type_propagado(self):
        from plugins.exemplo_plugin import fetch
        items = fetch(self.BASE_CONFIG)
        assert items[0]['source_type'] == 'exemplo_plugin'

    def test_id_tem_prefixo_frase(self):
        from plugins.exemplo_plugin import fetch
        items = fetch(self.BASE_CONFIG)
        assert items[0]['id'].startswith('frase-')

    def test_categoria_invalida_usa_fallback(self):
        from plugins.exemplo_plugin import fetch
        config = {**self.BASE_CONFIG, 'settings': {'categoria': 'inexistente'}}
        assert_valid_plugin_items(fetch(config))


# ── Trivia plugin (HTTP mockado) ──────────────────────────────────────────────

class TestTriviaPlugin:
    def _api_response(self, question='Qual a capital do Brasil?',
                      correct='Brasília', category='Geografia'):
        return {
            'response_code': 0,
            'results': [{
                'question':           question,
                'correct_answer':     correct,
                'incorrect_answers':  ['São Paulo', 'Rio de Janeiro', 'Salvador'],
                'category':           category,
                'difficulty':         'easy',
            }],
        }

    def _mock_get(self, response_data):
        mock = MagicMock()
        mock.json.return_value = response_data
        mock.raise_for_status = MagicMock()
        return mock

    def test_retorna_contrato_valido(self):
        from plugins.trivia import fetch
        with patch('plugins.trivia.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch({'settings': {'amount': 1}})
        assert_valid_plugin_items(items)

    def test_retorna_vazio_em_erro_de_rede(self):
        from plugins.trivia import fetch
        with patch('plugins.trivia.requests.get', side_effect=Exception("timeout")):
            items = fetch({'settings': {}})
        assert items == []

    def test_retorna_vazio_quando_api_falha(self):
        from plugins.trivia import fetch
        bad = {'response_code': 1, 'results': []}
        with patch('plugins.trivia.requests.get', return_value=self._mock_get(bad)):
            items = fetch({'settings': {}})
        assert items == []

    def test_html_entities_decodificadas(self):
        from plugins.trivia import fetch
        resp = self._api_response(question='Qual é &amp; foi?', correct='A &amp; B')
        with patch('plugins.trivia.requests.get', return_value=self._mock_get(resp)):
            items = fetch({'settings': {'amount': 1}})
        assert '&amp;' not in items[0]['title']
        assert '&amp;' not in items[0]['text']


# ── Copa do Mundo plugin (HTTP mockado) ───────────────────────────────────────

class TestCopaPlugin:
    BASE_CONFIG = {
        'id': 'copa', 'name': 'Copa do Mundo 2026', 'type': 'copa_mundo',
        'settings': {'api_key_env': 'FOOTBALL_DATA_API_KEY'},
    }

    def _api_response(self, matches=None):
        if matches is None:
            matches = [
                {
                    'utcDate': '2026-06-23T17:00:00Z',
                    'status': 'FINISHED',
                    'stage': 'GROUP_STAGE',
                    'group': 'GROUP_K',
                    'homeTeam': {'name': 'Portugal', 'shortName': 'Portugal'},
                    'awayTeam': {'name': 'Uzbekistan', 'shortName': 'Uzbekistan'},
                    'score': {'fullTime': {'home': 5, 'away': 0}},
                    'venue': 'MetLife Stadium',
                },
                {
                    'utcDate': '2026-06-24T22:00:00Z',
                    'status': 'SCHEDULED',
                    'stage': 'GROUP_STAGE',
                    'group': 'GROUP_C',
                    'homeTeam': {'name': 'Scotland', 'shortName': 'Scotland'},
                    'awayTeam': {'name': 'Brazil', 'shortName': 'Brazil'},
                    'score': {'fullTime': {'home': None, 'away': None}},
                    'venue': 'NRG Stadium',
                },
            ]
        return {'matches': matches}

    def _mock_get(self, data):
        mock = MagicMock()
        mock.json.return_value = data
        mock.raise_for_status = MagicMock()
        return mock

    def test_retorna_contrato_valido(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        assert_valid_plugin_items(items)

    def test_retorna_um_item(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        assert len(items) == 1

    def test_texto_contem_resultado_encerrado(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        text = items[0]['text']
        assert 'Portugal' in text
        assert '5' in text
        assert 'RESULTADOS RECENTES' in text

    def test_texto_contem_jogo_agendado(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        text = items[0]['text']
        assert 'Brasil' in text
        assert 'a jogar' in text

    def test_texto_contem_estadio_e_cidade(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        text = items[0]['text']
        assert 'MetLife Stadium' in text
        assert 'East Rutherford' in text

    def test_url_vazia(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        assert items[0]['url'] == ''

    def test_retorna_vazio_sem_api_key(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.delenv('FOOTBALL_DATA_API_KEY', raising=False)
        items = fetch(self.BASE_CONFIG)
        assert items == []

    def test_retorna_vazio_em_erro_de_rede(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get', side_effect=Exception('timeout')):
            items = fetch(self.BASE_CONFIG)
        assert items == []

    def test_retorna_vazio_sem_jogos_no_periodo(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get({'matches': []})):
            items = fetch(self.BASE_CONFIG)
        assert items == []

    def test_traduz_nome_do_time(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        assert 'Brasil' in items[0]['text']
        assert 'Brazil' not in items[0]['text']

    def test_source_type_propagado(self, monkeypatch):
        from plugins.copa_mundo import fetch
        monkeypatch.setenv('FOOTBALL_DATA_API_KEY', 'test-key')
        with patch('plugins.copa_mundo.requests.get',
                   return_value=self._mock_get(self._api_response())):
            items = fetch(self.BASE_CONFIG)
        assert items[0]['source_type'] == 'copa_mundo'
