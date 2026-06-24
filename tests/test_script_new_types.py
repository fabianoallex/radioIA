"""Testa os novos tipos de fonte em generate_script(): utility e combined.

Segue o mesmo padrão de test_script_context.py:
- litellm.completion é mockado — o LLM não é chamado de verdade
- Verifica o conteúdo do prompt enviado ao LLM
"""

import pytest
import litellm
from unittest.mock import MagicMock
from src.script_generator import generate_script, _build_combined_card


@pytest.fixture
def narrators():
    return [
        {'name': 'Ana',  'voice': 'pt-BR-FranciscaNeural', 'personality': 'animada'},
        {'name': 'João', 'voice': 'pt-BR-AntonioNeural',   'personality': 'direto'},
    ]


def _mock_completion(captured: dict):
    def _fn(**kwargs):
        captured['prompt'] = kwargs['messages'][0]['content']
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '[LOCUTOR_A]: Fala de teste.'
        return resp
    return _fn


def _utility_item(content='[CLIMA]\nCuiabá: céu limpo, 34°C'):
    return {
        'id': 'utility', 'title': 'Resumo do Dia', 'text': content,
        'source_type': 'utility', 'source_name': 'Resumo do Dia',
        'url': '', 'views': 0, 'comments': [], 'channel': 'Resumo do Dia', 'published_at': '',
    }


def _news_item(n=1, source_type='rss'):
    return {
        'id': f'item-{n}', 'title': f'Notícia {n}', 'url': f'https://exemplo.com/{n}',
        'text': f'Conteúdo da notícia {n}.', 'source_name': 'G1',
        'source_type': source_type, 'published_at': '2026-06-13',
        'views': 0, 'comments': [], 'channel': 'G1',
    }


class TestUtilityPrompt:
    def test_utility_data_appears_in_prompt(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        content = '[CLIMA]\nCuiabá: céu limpo, 34°C'
        generate_script([_utility_item(content)], narrators, {'type': 'utility', 'name': 'Resumo'})
        assert content in captured['prompt']

    def test_utility_prompt_has_tts_formatting_rules(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([_utility_item()], narrators, {'type': 'utility', 'name': 'Resumo'})
        prompt = captured['prompt']
        assert 'trinta e quatro graus' in prompt
        assert 'vírgula' in prompt.lower() or 'centavos' in prompt

    def test_utility_prompt_ends_with_roteiro(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([_utility_item()], narrators, {'type': 'utility', 'name': 'Resumo'})
        assert captured['prompt'].endswith('Roteiro:')

    def test_utility_context_injected(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script(
            [_utility_item()], narrators,
            {'type': 'utility', 'name': 'Resumo', 'context': 'foco no agronegócio'},
        )
        assert 'INSTRUÇÃO DO PRODUTOR: foco no agronegócio' in captured['prompt']

    def test_utility_narrator_names_in_prompt(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([_utility_item()], narrators, {'type': 'utility', 'name': 'Resumo'})
        assert 'Ana' in captured['prompt']
        assert 'João' in captured['prompt']


class TestCombinedPrompt:
    def test_combined_item_content_in_prompt(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        item = _news_item(1)
        generate_script([item], narrators, {'type': 'combined', 'name': 'Bom Dia'})
        assert 'Notícia 1' in captured['prompt']
        assert 'Conteúdo da notícia 1' in captured['prompt']

    def test_combined_prompt_ends_with_roteiro(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([_news_item()], narrators, {'type': 'combined', 'name': 'Bom Dia'})
        assert captured['prompt'].endswith('Roteiro:')

    def test_combined_context_injected(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script(
            [_news_item()], narrators,
            {'type': 'combined', 'name': 'Bom Dia', 'context': 'tom animado, foco no dia'},
        )
        assert 'INSTRUÇÃO DO PRODUTOR: tom animado, foco no dia' in captured['prompt']

    def test_combined_multiple_items_all_in_prompt(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        items = [_news_item(1), _news_item(2, source_type='youtube')]
        generate_script(items, narrators, {'type': 'combined', 'name': 'Bom Dia'})
        assert 'Notícia 1' in captured['prompt']
        assert 'Notícia 2' in captured['prompt']


class TestCopaMundoPrompt:
    CONTENT = (
        '[RESULTADOS RECENTES]\n'
        'Data: 23 de junho, terça-feira | Horário: 14:00 (Brasília) | Fase: Fase de Grupos | '
        'Grupo: Grupo K | Jogo: Portugal x Uzbequistão | Resultado: Portugal 5 x 0 Uzbequistão | '
        'Estádio: MetLife Stadium | Local: East Rutherford / Nova York\n'
        '[JOGOS DE HOJE]\n'
        'Data: 24 de junho, quarta-feira | Horário: 19:00 (Brasília) | Fase: Fase de Grupos | '
        'Grupo: Grupo C | Jogo: Escócia x Brasil | Resultado: a jogar | '
        'Estádio: NRG Stadium | Local: Houston'
    )

    def _copa_item(self):
        return {
            'id': 'copa-mundo-2026-06-24', 'title': 'Copa do Mundo 2026 — Resultados e Agenda',
            'text': self.CONTENT, 'url': '', 'source_name': 'Copa do Mundo 2026',
            'source_type': 'copa_mundo', 'published_at': '2026-06-24',
            'views': 0, 'comments': [], 'channel': 'Copa do Mundo 2026',
        }

    def test_dados_aparecem_no_prompt(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([self._copa_item()], narrators,
                        {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026'})
        assert 'Portugal' in captured['prompt']
        assert 'Brasil' in captured['prompt']
        assert 'RESULTADOS RECENTES' in captured['prompt']

    def test_prompt_termina_com_roteiro(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([self._copa_item()], narrators,
                        {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026'})
        assert captured['prompt'].endswith('Roteiro:')

    def test_prompt_nao_menciona_video_ou_canal(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([self._copa_item()], narrators,
                        {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026'})
        prompt = captured['prompt'].lower()
        assert 'link do video' not in prompt
        assert 'visualizações' not in prompt
        assert 'canal:' not in prompt

    def test_prompt_nao_usa_marcadores_item_n(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([self._copa_item()], narrators,
                        {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026'})
        assert 'NÃO use marcadores [ITEM_N]' in captured['prompt']

    def test_prompt_instrui_variacao_de_linguagem(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([self._copa_item()], narrators,
                        {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026'})
        assert 'VARIAÇÃO DE LINGUAGEM' in captured['prompt']

    def test_nomes_dos_narradores_no_prompt(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script([self._copa_item()], narrators,
                        {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026'})
        assert 'Ana' in captured['prompt']
        assert 'João' in captured['prompt']

    def test_context_produtor_injetado(self, narrators, monkeypatch):
        captured = {}
        monkeypatch.setattr(litellm, 'completion', _mock_completion(captured))
        generate_script(
            [self._copa_item()], narrators,
            {'type': 'copa_mundo', 'name': 'Copa do Mundo 2026',
             'context': 'foco nos jogos do Brasil'},
        )
        assert 'INSTRUÇÃO DO PRODUTOR: foco nos jogos do Brasil' in captured['prompt']


class TestBuildCombinedCard:
    def test_rss_item_labeled_noticia(self):
        card = _build_combined_card(1, _news_item(1, 'rss'))
        assert 'Notícia 1' in card

    def test_youtube_item_labeled_video(self):
        card = _build_combined_card(1, _news_item(1, 'youtube'))
        assert 'Vídeo 1' in card

    def test_clipping_item_labeled_clipping(self):
        card = _build_combined_card(1, _news_item(1, 'clipping'))
        assert 'Clipping 1' in card

    def test_unknown_type_labeled_item(self):
        card = _build_combined_card(1, _news_item(1, 'desconhecido'))
        assert 'Item 1' in card

    def test_card_contains_title(self):
        card = _build_combined_card(3, _news_item(3))
        assert 'Notícia 3' in card

    def test_card_contains_text_when_present(self):
        card = _build_combined_card(1, _news_item(1))
        assert 'Conteúdo da notícia 1' in card

    def test_card_contains_source_name(self):
        card = _build_combined_card(1, _news_item(1))
        assert 'G1' in card
