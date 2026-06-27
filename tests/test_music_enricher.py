"""Testa src/sources/music_enricher.py.

Cobre lógica pura (_sanitize, _build_filename), I/O de backup JSON e operações
de arquivo (rename/restore). Não faz chamadas de rede — MusicBrainz e Cover Art
Archive são excluídos intencionalmente.
"""

import os
import pytest
import src.sources.music_enricher as enricher


# ── fixture global ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_backup(tmp_path, monkeypatch):
    """Redireciona BACKUP_FILE para diretório temporário em todos os testes."""
    monkeypatch.setattr(enricher, 'BACKUP_FILE', str(tmp_path / 'metadata_backup.json'))


# ── _sanitize ─────────────────────────────────────────────────────────────────

class TestSanitize:
    def test_removes_backslash(self):
        assert '\\' not in enricher._sanitize('AC\\DC')

    def test_removes_forward_slash(self):
        assert '/' not in enricher._sanitize('and/or')

    def test_removes_colon(self):
        assert ':' not in enricher._sanitize('Title: Subtitle')

    def test_removes_all_windows_invalid_chars(self):
        result = enricher._sanitize('file*name?"<test>|pipe')
        for ch in r'\/:*?"<>|':
            assert ch not in result

    def test_replaces_invalid_with_underscore(self):
        assert enricher._sanitize('a:b') == 'a_b'

    def test_strips_leading_trailing_dots_and_spaces(self):
        assert enricher._sanitize('  .name. ') == 'name'

    def test_preserves_normal_chars(self):
        assert enricher._sanitize('Guns N Roses') == 'Guns N Roses'

    def test_preserves_accented_chars(self):
        assert enricher._sanitize('João & Maria') == 'João & Maria'

    def test_empty_string(self):
        assert enricher._sanitize('') == ''


# ── _build_filename ───────────────────────────────────────────────────────────

class TestBuildFilename:
    def _tags(self, title='Song', artist='Artist', album='Album'):
        return {'title': title, 'artist': artist, 'album': album}

    def test_artist_title_pattern(self):
        assert enricher._build_filename(self._tags(), 'artist_title') == 'Artist - Song'

    def test_artist_album_title_pattern(self):
        assert enricher._build_filename(self._tags(), 'artist_album_title') == 'Artist - Album - Song'

    def test_missing_artist_uses_title_only(self):
        assert enricher._build_filename(self._tags(artist=''), 'artist_title') == 'Song'

    def test_missing_album_skips_album_field(self):
        result = enricher._build_filename(self._tags(album=''), 'artist_album_title')
        assert result == 'Artist - Song'

    def test_missing_title_returns_none(self):
        assert enricher._build_filename(self._tags(title=''), 'artist_title') is None

    def test_all_fields_missing_returns_none(self):
        assert enricher._build_filename({'title': '', 'artist': '', 'album': ''}, 'artist_title') is None

    def test_unknown_pattern_falls_back_to_artist_title(self):
        result = enricher._build_filename(self._tags(), 'nonexistent')
        assert result == 'Artist - Song'

    def test_invalid_chars_in_tags_are_sanitized(self):
        tags   = self._tags(artist='AC/DC', title='Highway: To Hell')
        result = enricher._build_filename(tags, 'artist_title')
        assert '/' not in result
        assert ':' not in result
        assert 'AC_DC' in result
        assert 'Highway_ To Hell' in result

    def test_only_title_produces_single_part(self):
        result = enricher._build_filename({'title': 'Song', 'artist': '', 'album': ''}, 'artist_title')
        assert result == 'Song'
        assert ' - ' not in result


# ── backup JSON I/O ───────────────────────────────────────────────────────────

class TestBackupIO:
    def test_load_returns_empty_when_no_file(self):
        assert enricher._load_backup() == {}

    def test_save_and_load_roundtrip(self):
        data = {'/path/song.mp3': {'title': 'T', 'artist': 'A', 'album': 'B', 'apic': None}}
        enricher._save_backup(data)
        assert enricher._load_backup() == data

    def test_list_backup_excludes_renames_key(self):
        enricher._save_backup({
            '/path/song.mp3': {'title': 'T', 'artist': 'A', 'album': 'B',
                                'apic': None, 'backed_up_at': '2026-01-01T00:00:00'},
            '_renames': {'/new.mp3': '/old.mp3'},
        })
        entries = enricher.list_backup()
        assert len(entries) == 1
        assert entries[0]['path'] == '/path/song.mp3'

    def test_list_backup_fields_present(self):
        enricher._save_backup({
            '/path/song.mp3': {'title': 'T', 'artist': 'A', 'album': 'B',
                                'apic': 'abc123', 'backed_up_at': '2026-06-25T10:00:00'},
        })
        entry = enricher.list_backup()[0]
        assert entry['title']        == 'T'
        assert entry['artist']       == 'A'
        assert entry['album']        == 'B'
        assert entry['has_apic']     is True
        assert entry['backed_up_at'] == '2026-06-25T10:00:00'

    def test_list_backup_has_apic_false_when_none(self):
        enricher._save_backup({
            '/path/song.mp3': {'title': 'T', 'artist': 'A', 'album': 'B',
                                'apic': None, 'backed_up_at': ''},
        })
        assert enricher.list_backup()[0]['has_apic'] is False

    def test_list_backup_empty_when_only_renames(self):
        enricher._save_backup({'_renames': {'/new.mp3': '/old.mp3'}})
        assert enricher.list_backup() == []

    def test_list_renames_empty_when_no_backup(self):
        assert enricher.list_renames() == []

    def test_list_renames_returns_entries(self):
        enricher._save_backup({'_renames': {'/new/path.mp3': '/old/path.mp3'}})
        entries = enricher.list_renames()
        assert len(entries) == 1
        assert entries[0]['current_path']  == '/new/path.mp3'
        assert entries[0]['original_path'] == '/old/path.mp3'

    def test_list_renames_multiple_entries(self):
        enricher._save_backup({'_renames': {
            '/new/a.mp3': '/old/a.mp3',
            '/new/b.mp3': '/old/b.mp3',
        }})
        assert len(enricher.list_renames()) == 2


# ── backup_tags ───────────────────────────────────────────────────────────────

class TestBackupTags:
    def _mock_read(self, monkeypatch, **kwargs):
        tags = {'title': 'T', 'artist': 'A', 'album': 'B', 'apic': None, **kwargs}
        monkeypatch.setattr(enricher, '_read_current_tags', lambda p: tags)

    def test_saves_entry_to_backup(self, monkeypatch):
        self._mock_read(monkeypatch)
        enricher.backup_tags('/fake/song.mp3')
        entries = enricher.list_backup()
        assert len(entries) == 1

    def test_saved_entry_has_correct_path(self, monkeypatch):
        self._mock_read(monkeypatch)
        enricher.backup_tags('/fake/song.mp3')
        assert enricher.list_backup()[0]['path'] == os.path.abspath('/fake/song.mp3')

    def test_backed_up_at_is_set(self, monkeypatch):
        self._mock_read(monkeypatch)
        enricher.backup_tags('/fake/song.mp3')
        assert enricher.list_backup()[0]['backed_up_at'] != ''

    def test_overwrites_existing_entry(self, monkeypatch):
        self._mock_read(monkeypatch, title='Old')
        enricher.backup_tags('/fake/song.mp3')
        self._mock_read(monkeypatch, title='New')
        enricher.backup_tags('/fake/song.mp3')
        entries = enricher.list_backup()
        assert len(entries) == 1
        assert entries[0]['title'] == 'New'


# ── rename_file ───────────────────────────────────────────────────────────────

class TestRenameFile:
    def _mock_tags(self, monkeypatch, title='Song', artist='Artist', album='Album'):
        monkeypatch.setattr(
            enricher, '_read_current_tags',
            lambda p: {'title': title, 'artist': artist, 'album': album, 'apic': None},
        )

    def test_dry_run_returns_dry_run_status(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'unknown.mp3'
        f.write_bytes(b'')
        result = enricher.rename_file(str(f), dry_run=True)
        assert result['status']   == 'dry_run'
        assert result['new_name'] == 'Artist - Song.mp3'

    def test_dry_run_does_not_move_file(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'unknown.mp3'
        f.write_bytes(b'')
        enricher.rename_file(str(f), dry_run=True)
        assert f.exists()

    def test_dry_run_does_not_write_backup(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'unknown.mp3'
        f.write_bytes(b'')
        enricher.rename_file(str(f), dry_run=True)
        assert enricher._load_backup() == {}

    def test_rename_moves_file(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'track01.mp3'
        f.write_bytes(b'')
        result = enricher.rename_file(str(f), dry_run=False)
        assert result['status']   == 'ok'
        assert result['new_name'] == 'Artist - Song.mp3'
        assert (tmp_path / 'Artist - Song.mp3').exists()
        assert not f.exists()

    def test_rename_saves_original_in_backup(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'track01.mp3'
        f.write_bytes(b'')
        enricher.rename_file(str(f), dry_run=False)
        renames  = enricher._load_backup().get('_renames', {})
        new_path = os.path.abspath(str(tmp_path / 'Artist - Song.mp3'))
        assert new_path in renames
        assert renames[new_path] == os.path.abspath(str(f))

    def test_unchanged_when_name_already_correct(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'Artist - Song.mp3'
        f.write_bytes(b'')
        result = enricher.rename_file(str(f), dry_run=False)
        assert result['status'] == 'unchanged'
        assert f.exists()

    def test_skip_when_title_missing(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch, title='')
        f = tmp_path / 'track01.mp3'
        f.write_bytes(b'')
        result = enricher.rename_file(str(f), dry_run=False)
        assert result['status'] == 'skip'
        assert f.exists()

    def test_collision_when_target_exists(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f      = tmp_path / 'track01.mp3'
        target = tmp_path / 'Artist - Song.mp3'
        f.write_bytes(b'')
        target.write_bytes(b'')
        result = enricher.rename_file(str(f), dry_run=False)
        assert result['status'] == 'collision'
        assert f.exists()

    def test_collision_does_not_write_backup(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f      = tmp_path / 'track01.mp3'
        target = tmp_path / 'Artist - Song.mp3'
        f.write_bytes(b'')
        target.write_bytes(b'')
        enricher.rename_file(str(f), dry_run=False)
        assert enricher._load_backup() == {}

    def test_artist_album_title_pattern(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'track01.mp3'
        f.write_bytes(b'')
        result = enricher.rename_file(str(f), pattern='artist_album_title', dry_run=True)
        assert result['new_name'] == 'Artist - Album - Song.mp3'

    def test_preserves_file_extension(self, monkeypatch, tmp_path):
        self._mock_tags(monkeypatch)
        f = tmp_path / 'track01.flac'
        f.write_bytes(b'')
        result = enricher.rename_file(str(f), dry_run=True)
        assert result['new_name'].endswith('.flac')


# ── _parse_filename ───────────────────────────────────────────────────────────

class TestParseFilename:
    def test_artist_and_title(self):
        assert enricher._parse_filename('Engenheiros do Hawaii - Números') == \
               ('Engenheiros do Hawaii', 'Números')

    def test_strips_leading_track_number_space(self):
        artist, title = enricher._parse_filename('03 Song Title')
        assert artist == ''
        assert title  == 'Song Title'

    def test_strips_leading_number_dot_dash(self):
        artist, title = enricher._parse_filename('13 - Terra de Gigantes - Números')
        assert artist == 'Terra de Gigantes'
        assert title  == 'Números'

    def test_strips_parenthetical_suffix(self):
        artist, title = enricher._parse_filename('Artist - Title (ao vivo)')
        assert artist == 'Artist'
        assert title  == 'Title'

    def test_strips_bracket_suffix(self):
        _, title = enricher._parse_filename('Artist - Title [live]')
        assert title == 'Title'

    def test_strips_part_suffix(self):
        _, title = enricher._parse_filename(
            'Luz Da Minha Vida - Ultimo Adeus - Part.Bruno e Marrone')
        assert 'Bruno' not in title
        assert 'Part'  not in title

    def test_strips_feat_suffix(self):
        _, title = enricher._parse_filename('Title - feat. Guest Artist')
        assert 'Guest' not in title

    def test_parenthetical_number_at_end(self):
        artist, title = enricher._parse_filename('mILIONARIO E jOSE rICO (10)')
        assert artist    == ''
        assert '(10)' not in title
        assert 'rICO'  in title

    def test_no_separator_returns_empty_artist(self):
        artist, title = enricher._parse_filename('SOSSEGO')
        assert artist == ''
        assert title  == 'SOSSEGO'

    def test_three_parts_uses_first_and_last(self):
        artist, title = enricher._parse_filename('Artist - Album - Title')
        assert artist == 'Artist'
        assert title  == 'Title'

    def test_plain_artist_title(self):
        assert enricher._parse_filename('Artist - Title') == ('Artist', 'Title')


# ── _artist_similarity ────────────────────────────────────────────────────────

class TestArtistSimilarity:
    def test_identical(self):
        assert enricher._artist_similarity('Engenheiros do Hawaii', 'Engenheiros do Hawaii') == 1.0

    def test_completely_different(self):
        assert enricher._artist_similarity('X-Men Soundtrack', 'Milionario e Jose Rico') == 0.0

    def test_partial_match(self):
        sim = enricher._artist_similarity('Milionario e Jose Rico', 'Milionario Jose Rico')
        assert sim > 0.5

    def test_empty_first_returns_zero(self):
        assert enricher._artist_similarity('', 'Artist') == 0.0

    def test_empty_second_returns_zero(self):
        assert enricher._artist_similarity('Artist', '') == 0.0

    def test_both_empty_returns_zero(self):
        assert enricher._artist_similarity('', '') == 0.0

    def test_single_word_match(self):
        assert enricher._artist_similarity('Sossego', 'Sossego') == 1.0

    def test_case_insensitive(self):
        assert enricher._artist_similarity('ARTIST', 'artist') == 1.0


# ── restore_rename ────────────────────────────────────────────────────────────

class TestRestoreRename:
    def _setup(self, tmp_path, original_name='original.mp3', renamed_name='Artist - Song.mp3'):
        original = tmp_path / original_name
        renamed  = tmp_path / renamed_name
        renamed.write_bytes(b'')
        enricher._save_backup({
            '_renames': {
                str(renamed.resolve()): str(original.resolve()),
            }
        })
        return original, renamed

    def test_restores_original_filename(self, tmp_path):
        original, renamed = self._setup(tmp_path)
        result = enricher.restore_rename(str(renamed))
        assert result['status'] == 'ok'
        assert original.exists()
        assert not renamed.exists()

    def test_removes_entry_from_backup(self, tmp_path):
        _, renamed = self._setup(tmp_path)
        enricher.restore_rename(str(renamed))
        assert enricher.list_renames() == []

    def test_not_found_when_no_backup_entry(self, tmp_path):
        f = tmp_path / 'some.mp3'
        f.write_bytes(b'')
        result = enricher.restore_rename(str(f))
        assert result['status'] == 'not_found'

    def test_collision_when_original_already_exists(self, tmp_path):
        original, renamed = self._setup(tmp_path)
        original.write_bytes(b'')   # cria o arquivo original também
        result = enricher.restore_rename(str(renamed))
        assert result['status'] == 'collision'
        assert renamed.exists()

    def test_collision_keeps_backup_entry(self, tmp_path):
        original, renamed = self._setup(tmp_path)
        original.write_bytes(b'')
        enricher.restore_rename(str(renamed))
        assert len(enricher.list_renames()) == 1

    def test_error_when_current_file_missing(self, tmp_path):
        original, renamed = self._setup(tmp_path)
        renamed.unlink()   # remove o arquivo atual antes de restaurar
        result = enricher.restore_rename(str(renamed))
        assert result['status'] == 'error'
