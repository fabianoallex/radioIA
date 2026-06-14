"""Testa _format_data_for_prompt() de src/sources/utility.py.

Função pura: dict de dados coletados → bloco de texto estruturado para o LLM.
"""

import pytest
from src.sources.utility import _format_data_for_prompt


def _empty_data():
    return {'clima': [], 'previsao': [], 'sol': None,
            'cambio': [], 'bolsa': {}, 'loterias': [], 'futebol': {}}


class TestFormatDataForPrompt:
    def test_empty_data_returns_empty_string(self):
        assert _format_data_for_prompt(_empty_data()) == ''

    def test_clima_section_present(self):
        data = {**_empty_data(), 'clima': [{
            'city': 'Cuiabá', 'temp': 34, 'temp_min': 28, 'temp_max': 37,
            'feels_like': 38, 'description': 'céu limpo', 'humidity': 35,
        }]}
        result = _format_data_for_prompt(data)
        assert '[CLIMA]' in result
        assert 'Cuiabá' in result
        assert '34°C' in result
        assert 'umidade 35%' in result

    def test_previsao_section_with_rain(self):
        data = {**_empty_data(), 'previsao': [{
            'city': 'São Paulo', 'label': 'amanhã', 'desc': 'nublado',
            'temp_min': 17, 'temp_max': 23, 'rain_prob': 80,
        }]}
        result = _format_data_for_prompt(data)
        assert '[PREVISÃO]' in result
        assert 'São Paulo' in result
        assert 'chance de chuva 80%' in result

    def test_previsao_section_no_rain_below_threshold(self):
        data = {**_empty_data(), 'previsao': [{
            'city': 'Cuiabá', 'label': 'amanhã', 'desc': 'ensolarado',
            'temp_min': 26, 'temp_max': 36, 'rain_prob': 10,
        }]}
        result = _format_data_for_prompt(data)
        assert 'chance de chuva' not in result

    def test_sol_section(self):
        data = {**_empty_data(), 'sol': {
            'sunrise': '06h14', 'sunset': '17h47',
            'day_length_h': 11, 'day_length_m': 33,
        }}
        result = _format_data_for_prompt(data)
        assert '[SOL]' in result
        assert '06h14' in result
        assert '17h47' in result
        assert '11h33min' in result

    def test_cambio_section(self):
        data = {**_empty_data(), 'cambio': [
            {'pair': 'USD-BRL', 'code': 'USD', 'bid': 5.23, 'pct_change': 0.3},
            {'pair': 'EUR-BRL', 'code': 'EUR', 'bid': 5.89, 'pct_change': -0.1},
        ]}
        result = _format_data_for_prompt(data)
        assert '[CÂMBIO]' in result
        assert 'USD-BRL' in result
        assert 'R$ 5.23' in result
        assert 'EUR-BRL' in result

    def test_bolsa_section_with_movers(self):
        data = {**_empty_data(), 'bolsa': {
            'pontos': 132500, 'change': 0.8,
            'altas':  [{'ticker': 'PETR4', 'change': 2.1}],
            'baixas': [{'ticker': 'BBAS3', 'change': -1.2}],
        }}
        result = _format_data_for_prompt(data)
        assert '[BOLSA' in result
        assert '132,500' in result or '132500' in result
        assert 'PETR4' in result
        assert 'BBAS3' in result

    def test_bolsa_absent_when_no_pontos(self):
        data = {**_empty_data(), 'bolsa': {'pontos': None, 'change': None, 'altas': [], 'baixas': []}}
        result = _format_data_for_prompt(data)
        assert '[BOLSA' not in result

    def test_loteria_acumulada(self):
        data = {**_empty_data(), 'loterias': [{
            'name': 'Mega-Sena', 'numero': '2750', 'data': '10 de junho',
            'dezenas': '05, 11, 23, 34, 45, 56',
            'acumulado': True, 'ganhadores': 0,
            'valor_premio': 0, 'proximo_valor': 85_000_000,
            'proxima_data': '14 de junho',
        }]}
        result = _format_data_for_prompt(data)
        assert '[LOTERIAS]' in result
        assert 'Mega-Sena' in result
        assert 'Acumulou' in result
        assert '85 milhões' in result

    def test_loteria_com_ganhadores(self):
        data = {**_empty_data(), 'loterias': [{
            'name': 'Lotofácil', 'numero': '3100', 'data': '12 de junho',
            'dezenas': '01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15',
            'acumulado': False, 'ganhadores': 3,
            'valor_premio': 500_000, 'proximo_valor': 2_000_000,
            'proxima_data': '14 de junho',
        }]}
        result = _format_data_for_prompt(data)
        assert '3 ganhador(es)' in result
        assert 'Acumulou' not in result

    def test_futebol_ontem_e_hoje(self):
        data = {**_empty_data(), 'futebol': {
            'name': 'Copa do Mundo',
            'live': [],
            'finished': [{'home': 'Brasil', 'away': 'Argentina', 'home_score': 2, 'away_score': 1, 'time': '20:00'}],
            'today':    [{'home': 'França',  'away': 'Espanha',   'home_score': None, 'away_score': None, 'time': '16:00'}],
        }}
        result = _format_data_for_prompt(data)
        assert '[FUTEBOL' in result
        assert 'Brasil' in result
        assert '2x1' in result
        assert 'França' in result
        assert 'Hoje às 16:00' in result

    def test_futebol_ao_vivo(self):
        data = {**_empty_data(), 'futebol': {
            'name': 'Copa do Mundo', 'live': [
                {'home': 'Alemanha', 'away': 'Itália', 'home_score': 1, 'away_score': 0, 'time': '18:00'}
            ], 'finished': [], 'today': [],
        }}
        result = _format_data_for_prompt(data)
        assert 'AO VIVO' in result
        assert 'Alemanha' in result

    def test_multiple_sections_all_present(self):
        data = {
            'clima': [{'city': 'SP', 'temp': 22, 'temp_min': 18, 'temp_max': 26,
                       'feels_like': 24, 'description': 'nublado', 'humidity': 68}],
            'previsao': [],
            'sol': None,
            'cambio': [{'pair': 'USD-BRL', 'code': 'USD', 'bid': 5.23, 'pct_change': 0.3}],
            'bolsa': {'pontos': 132500, 'change': 0.8, 'altas': [], 'baixas': []},
            'loterias': [],
            'futebol': {},
        }
        result = _format_data_for_prompt(data)
        assert '[CLIMA]' in result
        assert '[CÂMBIO]' in result
        assert '[BOLSA' in result
