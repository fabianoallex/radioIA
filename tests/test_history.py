import json
import pytest
import src.history as history_mod


@pytest.fixture(autouse=True)
def temp_history(tmp_path, monkeypatch):
    hist_file = str(tmp_path / 'history.json')
    monkeypatch.setattr(history_mod, 'HISTORY_PATH', hist_file)
    yield hist_file


class TestLoadSeenIds:
    def test_returns_empty_set_when_no_file(self):
        assert history_mod.load_seen_ids() == set()

    def test_returns_ids_from_existing_file(self, temp_history):
        with open(temp_history, 'w') as f:
            json.dump({'seen_ids': ['id1', 'id2', 'id3'], 'episodes': []}, f)
        assert history_mod.load_seen_ids() == {'id1', 'id2', 'id3'}

    def test_handles_missing_seen_ids_key(self, temp_history):
        with open(temp_history, 'w') as f:
            json.dump({'episodes': []}, f)
        assert history_mod.load_seen_ids() == set()

    def test_returns_set_not_list(self, temp_history):
        with open(temp_history, 'w') as f:
            json.dump({'seen_ids': ['id1'], 'episodes': []}, f)
        result = history_mod.load_seen_ids()
        assert isinstance(result, set)


class TestSaveEpisodeToHistory:
    def _video(self, vid_id, title='Título', channel='Canal'):
        return {'id': vid_id, 'title': title, 'channel': channel}

    def test_creates_file_when_not_exists(self, temp_history):
        history_mod.save_episode_to_history('ep1', [self._video('v1')])
        with open(temp_history) as f:
            data = json.load(f)
        assert 'v1' in data['seen_ids']

    def test_saves_episode_record(self, temp_history):
        history_mod.save_episode_to_history('2024-01-01/10-00_news', [self._video('v1')])
        with open(temp_history) as f:
            data = json.load(f)
        assert data['episodes'][0]['episode_id'] == '2024-01-01/10-00_news'
        assert data['episodes'][0]['videos'][0]['id'] == 'v1'

    def test_accumulates_ids_across_episodes(self, temp_history):
        history_mod.save_episode_to_history('ep1', [self._video('v1')])
        history_mod.save_episode_to_history('ep2', [self._video('v2')])
        seen = history_mod.load_seen_ids()
        assert 'v1' in seen
        assert 'v2' in seen

    def test_no_duplicate_ids(self, temp_history):
        history_mod.save_episode_to_history('ep1', [self._video('v1')])
        history_mod.save_episode_to_history('ep2', [self._video('v1')])
        with open(temp_history) as f:
            data = json.load(f)
        assert data['seen_ids'].count('v1') == 1

    def test_multiple_videos_per_episode(self, temp_history):
        videos = [self._video('v1'), self._video('v2'), self._video('v3')]
        history_mod.save_episode_to_history('ep1', videos)
        seen = history_mod.load_seen_ids()
        assert seen == {'v1', 'v2', 'v3'}

    def test_seen_ids_persists_across_loads(self, temp_history):
        history_mod.save_episode_to_history('ep1', [self._video('v1')])
        fresh_seen = history_mod.load_seen_ids()
        assert 'v1' in fresh_seen
