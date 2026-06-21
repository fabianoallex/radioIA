"""Testes para o sistema de status publicado/rascunho de episódios."""
import json
import os
from unittest.mock import patch, MagicMock

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_videos(ids):
    return [{'id': v, 'title': f'Titulo {v}', 'channel': 'Canal', 'url': f'http://ex.com/{v}',
              'views': 0, 'published_at': '', 'comments': []} for v in ids]


# ── save_episode_metadata: campo status ──────────────────────────────────────

class TestSaveEpisodeMetadataStatus:
    """save_episode_metadata deve gravar status correto no episode.json."""

    def _call(self, tmp_path, publish=True, **kw):
        from src.audio_mixer import save_episode_metadata
        out_dir = str(tmp_path)
        videos = _make_videos(['v1', 'v2'])
        save_episode_metadata(videos, 'script texto', out_dir,
                              duration_secs=120.0, source_name='YouTube',
                              publish=publish, **kw)
        with open(os.path.join(out_dir, 'episode.json'), encoding='utf-8') as f:
            return json.load(f)

    def test_publish_true_grava_published(self, tmp_path):
        meta = self._call(tmp_path, publish=True)
        assert meta['status'] == 'published'

    def test_publish_false_grava_draft(self, tmp_path):
        meta = self._call(tmp_path, publish=False)
        assert meta['status'] == 'draft'

    def test_padrao_e_published(self, tmp_path):
        from src.audio_mixer import save_episode_metadata
        videos = _make_videos(['v1'])
        save_episode_metadata(videos, 'script', str(tmp_path), duration_secs=60.0)
        with open(os.path.join(str(tmp_path), 'episode.json'), encoding='utf-8') as f:
            meta = json.load(f)
        assert meta['status'] == 'published'

    def test_status_e_primeira_chave(self, tmp_path):
        meta = self._call(tmp_path)
        keys = list(meta.keys())
        assert keys[0] == 'status'

    def test_generation_preservado_com_status(self, tmp_path):
        gen = {'model': 'deepseek/deepseek-chat', 'total_seconds': 30}
        meta = self._call(tmp_path, publish=False, generation=gen)
        assert meta['status'] == 'draft'
        assert meta['generation']['model'] == 'deepseek/deepseek-chat'

    def test_campos_obrigatorios_presentes(self, tmp_path):
        meta = self._call(tmp_path)
        for campo in ('status', 'source_name', 'duration_seconds', 'videos_covered', 'links'):
            assert campo in meta


# ── Lógica de remoção do histórico ───────────────────────────────────────────

class TestDeleteEpisodeHistoryCleanup:
    """A remoção de episódio deve limpar seen_ids e episodes do history.json."""

    def _build_history(self, tmp_path, episodes):
        """episodes: list of (ep_id, video_ids)"""
        seen = []
        eps = []
        for ep_id, vids in episodes:
            seen.extend(vids)
            eps.append({'episode_id': ep_id, 'videos': [{'id': v} for v in vids]})
        data = {'seen_ids': seen, 'episodes': eps}
        hist_path = tmp_path / 'history.json'
        hist_path.write_text(json.dumps(data), encoding='utf-8')
        return hist_path

    def _simulate_delete(self, hist_path, ep_id):
        """Mesma lógica usada em serve.py e api/routers/episodes.py."""
        hist = json.loads(hist_path.read_text(encoding='utf-8'))
        ep_entry = next((e for e in hist.get('episodes', [])
                         if e.get('episode_id') == ep_id), None)
        items_removed = 0
        if ep_entry:
            id_set = {v['id'] for v in ep_entry.get('videos', [])}
            hist['seen_ids'] = [i for i in hist.get('seen_ids', []) if i not in id_set]
            hist['episodes'] = [e for e in hist.get('episodes', [])
                                 if e.get('episode_id') != ep_id]
            items_removed = len(id_set)
            hist_path.write_text(json.dumps(hist), encoding='utf-8')
        return items_removed, json.loads(hist_path.read_text(encoding='utf-8'))

    def test_remove_seen_ids_do_episodio(self, tmp_path):
        hist_path = self._build_history(tmp_path, [
            ('2026-06-21/08-30_youtube', ['v1', 'v2']),
            ('2026-06-21/09-00_noticias', ['n1']),
        ])
        removed, hist = self._simulate_delete(hist_path, '2026-06-21/08-30_youtube')
        assert removed == 2
        assert 'v1' not in hist['seen_ids']
        assert 'v2' not in hist['seen_ids']
        assert 'n1' in hist['seen_ids']

    def test_remove_entrada_do_episodes(self, tmp_path):
        hist_path = self._build_history(tmp_path, [
            ('2026-06-21/08-30_youtube', ['v1']),
            ('2026-06-21/09-00_noticias', ['n1']),
        ])
        _, hist = self._simulate_delete(hist_path, '2026-06-21/08-30_youtube')
        ep_ids = [e['episode_id'] for e in hist['episodes']]
        assert '2026-06-21/08-30_youtube' not in ep_ids
        assert '2026-06-21/09-00_noticias' in ep_ids

    def test_episodio_inexistente_nao_altera_history(self, tmp_path):
        hist_path = self._build_history(tmp_path, [
            ('2026-06-21/08-30_youtube', ['v1']),
        ])
        removed, hist = self._simulate_delete(hist_path, '2026-06-21/99-99_fake')
        assert removed == 0
        assert 'v1' in hist['seen_ids']
        assert len(hist['episodes']) == 1

    def test_retorna_quantidade_de_itens_removidos(self, tmp_path):
        hist_path = self._build_history(tmp_path, [
            ('ep1', ['a', 'b', 'c']),
        ])
        removed, _ = self._simulate_delete(hist_path, 'ep1')
        assert removed == 3

    def test_historico_vazio_nao_falha(self, tmp_path):
        hist_path = tmp_path / 'history.json'
        hist_path.write_text(json.dumps({'seen_ids': [], 'episodes': []}), encoding='utf-8')
        removed, hist = self._simulate_delete(hist_path, 'qualquer/ep')
        assert removed == 0
        assert hist == {'seen_ids': [], 'episodes': []}


# ── _write_status: campo publicar ────────────────────────────────────────────

class TestWriteStatusPublicar:
    """_write_status deve incluir campo publicar no geracao_status.json."""

    def test_publicar_true_por_padrao(self, tmp_path):
        import main as radio_main
        status_file = str(tmp_path / 'status.json')
        with patch.object(radio_main, '_STATUS_FILE', status_file):
            with patch.object(radio_main, '_local_now') as mock_now:
                mock_now.return_value = MagicMock(
                    strftime=lambda fmt: '2026-06-21' if '%Y' in fmt else '10:00:00'
                )
                radio_main._write_status('youtube', 'YouTube', 'gerando')
        with open(status_file, encoding='utf-8') as f:
            data = json.load(f)
        assert data['publicar'] is True

    def test_publicar_false_quando_passado(self, tmp_path):
        import main as radio_main
        status_file = str(tmp_path / 'status.json')
        with patch.object(radio_main, '_STATUS_FILE', status_file):
            with patch.object(radio_main, '_local_now') as mock_now:
                mock_now.return_value = MagicMock(
                    strftime=lambda fmt: '2026-06-21' if '%Y' in fmt else '10:00:00'
                )
                radio_main._write_status('youtube', 'YouTube', 'concluido',
                                         ativo=False, publicar=False)
        with open(status_file, encoding='utf-8') as f:
            data = json.load(f)
        assert data['publicar'] is False
