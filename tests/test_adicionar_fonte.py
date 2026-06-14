"""Testa adicionar_fonte() de mcp_server.py.

Cobre: validações de erro (ID duplicado, tipo inválido, JSON inválido,
combined sem sources) e o caminho feliz (combined, rss, campos extras).
_load_config e _save_config são mockados para evitar I/O de disco.
"""

import json
import pytest

mcp_server = pytest.importorskip(
    'mcp_server',
    reason='mcp_server não importável (dependências MCP ausentes)',
)
adicionar_fonte = mcp_server.adicionar_fonte


def _config_vazio():
    return {'sources': []}


def _config_com_fonte(id_fonte='youtube'):
    return {'sources': [{'id': id_fonte, 'type': 'youtube', 'name': 'YouTube', 'enabled': True}]}


class TestAdicionarFonteErros:
    def test_id_duplicado(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_com_fonte('youtube'))
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('youtube', 'rss', 'Outro YouTube'))
        assert r['status'] == 'erro'
        assert 'ja existe' in r['mensagem']

    def test_tipo_invalido(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('nova', 'tipo-inventado', 'Nome'))
        assert r['status'] == 'erro'
        assert 'invalido' in r['mensagem'].lower()
        assert 'tipos_validos' in r

    def test_extras_json_invalido(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('nova', 'rss', 'Nome', extras='{chave sem aspas}'))
        assert r['status'] == 'erro'
        assert 'JSON' in r['mensagem']

    def test_combined_sem_sources(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('bom-dia', 'combined', 'Bom Dia'))
        assert r['status'] == 'erro'
        assert 'sources' in r['mensagem']

    def test_combined_extras_sem_sources(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('bom-dia', 'combined', 'Bom Dia', '{"model": "x"}'))
        assert r['status'] == 'erro'
        assert 'sources' in r['mensagem']


class TestAdicionarFonteSucesso:
    def test_combined_criado_com_sucesso(self, monkeypatch):
        salvo = {}
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: salvo.update(c))
        extras = json.dumps({'sources': ['noticias', 'youtube']})
        r = json.loads(adicionar_fonte('bom-dia', 'combined', 'Bom Dia MT', extras))
        assert r['status'] == 'ok'
        assert r['fonte']['id'] == 'bom-dia'
        assert r['fonte']['type'] == 'combined'
        assert r['fonte']['sources'] == ['noticias', 'youtube']

    def test_rss_criado_com_sucesso(self, monkeypatch):
        salvo = {}
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: salvo.update(c))
        feeds = [{'url': 'https://g1.globo.com/rss/g1/', 'name': 'G1'}]
        extras = json.dumps({'feeds': feeds})
        r = json.loads(adicionar_fonte('noticias-tech', 'rss', 'Tech News', extras))
        assert r['status'] == 'ok'
        assert r['fonte']['type'] == 'rss'
        assert r['fonte']['feeds'] == feeds

    def test_enabled_true_por_padrao(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        extras = json.dumps({'sources': ['noticias']})
        r = json.loads(adicionar_fonte('bom-dia', 'combined', 'Bom Dia', extras))
        assert r['fonte']['enabled'] is True

    def test_extras_model_e_context_incluidos(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        extras = json.dumps({
            'sources': ['noticias'],
            'model': 'claude-haiku-4-5-20251001',
            'context': 'tom animado',
        })
        r = json.loads(adicionar_fonte('bom-dia', 'combined', 'Bom Dia', extras))
        assert r['fonte']['model'] == 'claude-haiku-4-5-20251001'
        assert r['fonte']['context'] == 'tom animado'

    def test_fonte_salva_no_config(self, monkeypatch):
        salvo = {}
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: salvo.update(c))
        extras = json.dumps({'sources': ['noticias']})
        adicionar_fonte('bom-dia', 'combined', 'Bom Dia', extras)
        ids = [s['id'] for s in salvo['sources']]
        assert 'bom-dia' in ids

    def test_extras_vazio_aceito(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('meu-horoscopo', 'horoscopo', 'Horóscopo'))
        assert r['status'] == 'ok'

    def test_nome_correto_na_fonte(self, monkeypatch):
        monkeypatch.setattr(mcp_server, '_load_config', lambda: _config_vazio())
        monkeypatch.setattr(mcp_server, '_save_config', lambda c: None)
        r = json.loads(adicionar_fonte('meu-quiz', 'quiz', 'Quiz do Dia'))
        assert r['fonte']['name'] == 'Quiz do Dia'
