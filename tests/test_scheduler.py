import pytest
from unittest.mock import MagicMock
from scheduler import _entry_key, _entry_active_today, _fix_schedule_times


class TestEntryKey:
    def test_daily_entry_contains_time_and_sources(self):
        entry = {'time': '08:00', 'sources': ['noticias', 'musica']}
        key = _entry_key(entry)
        assert '08:00' in key
        assert 'daily' in key

    def test_sources_sorted_so_order_does_not_matter(self):
        e1 = {'time': '09:00', 'sources': ['a', 'b', 'c']}
        e2 = {'time': '09:00', 'sources': ['c', 'a', 'b']}
        assert _entry_key(e1) == _entry_key(e2)

    def test_dated_entry_uses_date_not_daily(self):
        entry = {'time': '11:00', 'date': '2026-06-11', 'sources': ['copa']}
        key = _entry_key(entry)
        assert '2026-06-11' in key
        assert 'daily' not in key

    def test_replay_entry_uses_replay_prefix(self):
        entry = {'time': '14:00', 'replay_of': 10}
        key = _entry_key(entry)
        assert 'replay:10' in key

    def test_days_sorted_so_order_does_not_matter(self):
        e1 = {'time': '07:00', 'sources': ['s'], 'days': ['mon', 'fri']}
        e2 = {'time': '07:00', 'sources': ['s'], 'days': ['fri', 'mon']}
        assert _entry_key(e1) == _entry_key(e2)

    def test_different_times_produce_different_keys(self):
        e1 = {'time': '07:00', 'sources': ['noticias']}
        e2 = {'time': '09:00', 'sources': ['noticias']}
        assert _entry_key(e1) != _entry_key(e2)

    def test_different_sources_produce_different_keys(self):
        e1 = {'time': '07:00', 'sources': ['noticias']}
        e2 = {'time': '07:00', 'sources': ['musica']}
        assert _entry_key(e1) != _entry_key(e2)


class TestEntryActiveToday:
    def test_no_days_field_always_active(self):
        assert _entry_active_today({'time': '08:00', 'sources': ['s']}) is True

    def test_empty_days_always_active(self):
        assert _entry_active_today({'days': []}) is True

    def test_matching_weekday_is_active(self, monkeypatch):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = 0  # segunda
        monkeypatch.setattr('scheduler.datetime', mock_dt)
        assert _entry_active_today({'days': ['mon']}) is True

    def test_non_matching_weekday_is_inactive(self, monkeypatch):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = 0  # segunda
        monkeypatch.setattr('scheduler.datetime', mock_dt)
        assert _entry_active_today({'days': ['tue', 'wed', 'thu']}) is False

    def test_one_of_multiple_days_matches(self, monkeypatch):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = 4  # sexta
        monkeypatch.setattr('scheduler.datetime', mock_dt)
        assert _entry_active_today({'days': ['mon', 'wed', 'fri']}) is True

    def test_weekend_days(self, monkeypatch):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = 6  # domingo
        monkeypatch.setattr('scheduler.datetime', mock_dt)
        assert _entry_active_today({'days': ['sat', 'sun']}) is True

    def test_days_are_case_insensitive(self, monkeypatch):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = 0  # segunda
        monkeypatch.setattr('scheduler.datetime', mock_dt)
        assert _entry_active_today({'days': ['MON']}) is True

    def test_workweek_excludes_weekend(self, monkeypatch):
        mock_dt = MagicMock()
        mock_dt.now.return_value.weekday.return_value = 5  # sábado
        monkeypatch.setattr('scheduler.datetime', mock_dt)
        assert _entry_active_today({'days': ['mon', 'tue', 'wed', 'thu', 'fri']}) is False


class TestFixScheduleTimes:
    """PyYAML parseia times >= 10:00 sem aspas como inteiros (ex: 10:30 -> 630).
    _fix_schedule_times normaliza de volta para HH:MM."""

    def test_integer_time_converted_to_hhmm(self):
        config = {'schedule': [{'time': 630, 'sources': ['noticias']}]}
        result = _fix_schedule_times(config)
        assert result['schedule'][0]['time'] == '10:30'

    def test_midnight_zero(self):
        config = {'schedule': [{'time': 0, 'sources': ['noticias']}]}
        result = _fix_schedule_times(config)
        assert result['schedule'][0]['time'] == '00:00'

    def test_hour_boundary(self):
        # 9:00 -> 540
        config = {'schedule': [{'time': 540, 'sources': ['s']}]}
        assert _fix_schedule_times(config)['schedule'][0]['time'] == '09:00'

    def test_string_time_unchanged(self):
        config = {'schedule': [{'time': '08:30', 'sources': ['s']}]}
        result = _fix_schedule_times(config)
        assert result['schedule'][0]['time'] == '08:30'

    def test_mixed_entries(self):
        config = {'schedule': [
            {'time': 630, 'sources': ['a']},   # 10:30
            {'time': '09:00', 'sources': ['b']},
            {'time': 450, 'sources': ['c']},   # 07:30
        ]}
        times = [e['time'] for e in _fix_schedule_times(config)['schedule']]
        assert times == ['10:30', '09:00', '07:30']

    def test_empty_schedule(self):
        config = {'schedule': []}
        assert _fix_schedule_times(config) == {'schedule': []}

    def test_no_schedule_key(self):
        config = {'radio': {'name': 'Test'}}
        result = _fix_schedule_times(config)
        assert result == {'radio': {'name': 'Test'}}

    def test_none_time_field_ignored(self):
        config = {'schedule': [{'sources': ['s']}]}  # sem campo time
        result = _fix_schedule_times(config)
        assert 'time' not in result['schedule'][0]
