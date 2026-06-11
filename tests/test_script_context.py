"""Testa a injeção de context (INSTRUCAO DO PRODUTOR) em generate_script().

O campo source_config['context'] deve aparecer no prompt enviado ao LLM,
imediatamente antes de 'Roteiro:', para qualquer tipo de source.
O LLM não é chamado de verdade — litellm.completion é substituído por mock.
"""

import pytest
import litellm
from unittest.mock import MagicMock
from src.script_generator import generate_script


@pytest.fixture
def narrators():
    return [{'name': 'Ana', 'voice': 'pt-BR-ThalitaMultilingualNeural', 'personality': 'curiosa'}]


@pytest.fixture
def item():
    return {
        'id':           'test-1',
        'title':        'Título de teste',
        'url':          'https://exemplo.com',
        'text':         'Texto de conteúdo.',
        'source_name':  'Fonte Teste',
        'source_type':  'rss',
        'published_at': '2026-06-11',
        'views':        0,
        'comments':     [],
        'channel':      'Canal Teste',
    }


def _mock_completion(captured: dict):
    def _fn(**kwargs):
        captured['prompt'] = kwargs['messages'][0]['content']
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '[LOCUTOR_A]: Fala de teste.'
        return resp
    return _fn


class TestContextInjection:
    def test_context_appears_in_prompt(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        generate_script(
            [item], narrators,
            {'type': 'rss', 'name': 'Notícias', 'context': 'foca nos impactos econômicos'},
        )

        assert 'INSTRUCAO DO PRODUTOR: foca nos impactos econômicos' in captured['prompt']

    def test_context_placed_immediately_before_roteiro(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        generate_script(
            [item], narrators,
            {'type': 'rss', 'name': 'Notícias', 'context': 'minha instrução'},
        )

        prompt = captured['prompt']
        instrucao_pos = prompt.index('INSTRUCAO DO PRODUTOR')
        roteiro_pos   = prompt.rindex('Roteiro:')
        assert instrucao_pos < roteiro_pos
        # Nada entre a instrução e Roteiro: além de espaços/newlines
        between = prompt[instrucao_pos:roteiro_pos]
        assert 'APRESENTADORES' not in between
        assert 'REGRAS' not in between

    def test_no_context_no_instrucao_block(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        generate_script([item], narrators, {'type': 'rss', 'name': 'Notícias'})

        assert 'INSTRUCAO DO PRODUTOR' not in captured['prompt']

    def test_empty_context_string_no_block(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        generate_script(
            [item], narrators,
            {'type': 'rss', 'name': 'Notícias', 'context': ''},
        )

        assert 'INSTRUCAO DO PRODUTOR' not in captured['prompt']

    def test_context_works_for_url_type(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        url_item = {**item, 'source_type': 'url'}
        generate_script(
            [url_item], narrators,
            {
                'type': 'url', 'name': 'Web',
                'context': 'extraia os pontos técnicos',
                'settings': {'url': 'https://exemplo.com'},
            },
        )

        assert 'INSTRUCAO DO PRODUTOR: extraia os pontos técnicos' in captured['prompt']

    def test_context_works_for_reddit_type(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        reddit_item = {**item, 'source_type': 'reddit', 'num_comments': 10}
        generate_script(
            [reddit_item], narrators,
            {'type': 'reddit', 'name': 'Reddit', 'context': 'público tech'},
        )

        assert 'INSTRUCAO DO PRODUTOR: público tech' in captured['prompt']

    def test_prompt_still_ends_with_roteiro(self, narrators, item, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))

        generate_script(
            [item], narrators,
            {'type': 'rss', 'name': 'Notícias', 'context': 'qualquer contexto'},
        )

        assert captured['prompt'].endswith('Roteiro:')
