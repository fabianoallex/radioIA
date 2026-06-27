import base64
import json
import os
import re
import time

import requests

BACKUP_FILE = os.path.join('music', 'metadata_backup.json')

_MB_API     = 'https://musicbrainz.org/ws/2'
_CAA_API    = 'https://coverartarchive.org'
_MB_HEADERS = {
    'User-Agent': 'RadioIA/1.0 (personal radio automation)',
    'Accept':     'application/json',
}
_MIN_SCORE = 80


# ── MusicBrainz search ────────────────────────────────────────────────────────

def _search_musicbrainz(title: str, artist: str) -> dict | None:
    parts = []
    if title:
        parts.append(f'recording:"{title}"')
    if artist:
        parts.append(f'artist:"{artist}"')
    if not parts:
        return None
    try:
        resp = requests.get(
            f'{_MB_API}/recording',
            params={'query': ' AND '.join(parts), 'fmt': 'json', 'limit': 5},
            headers=_MB_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        for rec in resp.json().get('recordings', []):
            if int(rec.get('score', 0)) < _MIN_SCORE:
                continue
            releases = rec.get('releases', [])
            if not releases:
                continue
            release   = releases[0]
            ac        = rec.get('artist-credit', [])
            mb_artist = ac[0].get('artist', {}).get('name', '') if ac else ''
            return {
                'title':        rec.get('title', ''),
                'artist':       mb_artist,
                'album':        release.get('title', ''),
                'release_mbid': release.get('id', ''),
                'score':        int(rec.get('score', 0)),
            }
    except Exception as e:
        print(f'  [musicbrainz] {e}')
    return None


def _fetch_cover_art(release_mbid: str) -> bytes | None:
    for size in ('500', '250'):
        try:
            resp = requests.get(
                f'{_CAA_API}/release/{release_mbid}/front-{size}',
                headers=_MB_HEADERS,
                timeout=15,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
    return None


# ── Tag I/O ───────────────────────────────────────────────────────────────────

def _read_current_tags(path: str) -> dict:
    title, artist, album, apic_b64 = '', '', '', None
    try:
        from mutagen import File as MutagenFile
        af = MutagenFile(path, easy=True)
        if af:
            title  = str(af.get('title',  [''])[0]).strip()
            artist = str(af.get('artist', [''])[0]).strip()
            album  = str(af.get('album',  [''])[0]).strip()
    except Exception:
        pass

    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.mp3':
            from mutagen.id3 import ID3
            tags = ID3(path)
            keys = [k for k in tags if k.startswith('APIC')]
            if keys:
                apic_b64 = base64.b64encode(tags[keys[0]].data).decode()
        elif ext == '.flac':
            from mutagen.flac import FLAC
            af2 = FLAC(path)
            if af2.pictures:
                apic_b64 = base64.b64encode(af2.pictures[0].data).decode()
        elif ext == '.m4a':
            from mutagen.mp4 import MP4
            af2 = MP4(path)
            covr = af2.get('covr', [])
            if covr:
                apic_b64 = base64.b64encode(bytes(covr[0])).decode()
        elif ext == '.ogg':
            from mutagen.oggvorbis import OggVorbis
            af2 = OggVorbis(path)
            blocks = af2.get('metadata_block_picture', [])
            if blocks:
                from mutagen.flac import Picture
                pic      = Picture(base64.b64decode(blocks[0]))
                apic_b64 = base64.b64encode(pic.data).decode()
    except Exception:
        pass

    return {'title': title, 'artist': artist, 'album': album, 'apic': apic_b64}


def _write_tags(path: str, title: str = None, artist: str = None,
                album: str = None, cover_bytes: bytes = None):
    ext = os.path.splitext(path)[1].lower()

    if ext == '.mp3':
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
        try:
            tags = ID3(path)
        except Exception:
            from mutagen.mp3 import MP3
            mp3 = MP3(path)
            mp3.add_tags()
            tags = mp3.tags
        if title  is not None: tags['TIT2'] = TIT2(encoding=3, text=title)
        if artist is not None: tags['TPE1'] = TPE1(encoding=3, text=artist)
        if album  is not None: tags['TALB'] = TALB(encoding=3, text=album)
        if cover_bytes is not None:
            for k in [k for k in list(tags.keys()) if k.startswith('APIC')]:
                del tags[k]
            tags['APIC:'] = APIC(encoding=3, mime='image/jpeg', type=3,
                                  desc='Cover', data=cover_bytes)
        tags.save(path)

    elif ext == '.flac':
        from mutagen.flac import FLAC, Picture
        af = FLAC(path)
        if title  is not None: af['title']  = [title]
        if artist is not None: af['artist'] = [artist]
        if album  is not None: af['album']  = [album]
        if cover_bytes is not None:
            pic = Picture()
            pic.type, pic.mime, pic.desc, pic.data = 3, 'image/jpeg', 'Cover', cover_bytes
            af.clear_pictures()
            af.add_picture(pic)
        af.save()

    elif ext == '.m4a':
        from mutagen.mp4 import MP4, MP4Cover
        af = MP4(path)
        if title  is not None: af['\xa9nam'] = [title]
        if artist is not None: af['\xa9ART'] = [artist]
        if album  is not None: af['\xa9alb'] = [album]
        if cover_bytes is not None:
            af['covr'] = [MP4Cover(cover_bytes, MP4Cover.FORMAT_JPEG)]
        af.save()

    elif ext == '.ogg':
        from mutagen.oggvorbis import OggVorbis
        af = OggVorbis(path)
        if title  is not None: af['title']  = [title]
        if artist is not None: af['artist'] = [artist]
        if album  is not None: af['album']  = [album]
        if cover_bytes is not None:
            from mutagen.flac import Picture
            pic = Picture()
            pic.type, pic.mime, pic.desc = 3, 'image/jpeg', ''
            pic.data = cover_bytes
            pic.width = pic.height = pic.depth = pic.colors = 0
            af['metadata_block_picture'] = [
                base64.b64encode(pic.write()).decode('ascii')
            ]
        af.save()

    else:
        raise ValueError(f'Formato não suportado para escrita de tags: {ext}')


# ── Backup ────────────────────────────────────────────────────────────────────

def _load_backup() -> dict:
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _save_backup(data: dict):
    os.makedirs(os.path.dirname(os.path.abspath(BACKUP_FILE)), exist_ok=True)
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _strip_apic(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k != 'apic'}


def backup_tags(path: str) -> dict:
    backup = _load_backup()
    entry  = _read_current_tags(path)
    entry['backed_up_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    backup[os.path.abspath(path)] = entry
    _save_backup(backup)
    return entry


# ── Filename parsing ──────────────────────────────────────────────────────────

def _parse_filename(name: str) -> tuple[str, str]:
    """
    Parse a music filename (without extension) into (artist, title).
    Handles track-number prefixes, parentheticals, and Part./Feat. suffixes.
    Returns ('', cleaned_name) when artist cannot be determined.
    """
    cleaned = name
    # Strip leading track number: "03 ", "03. ", "03 - "
    cleaned = re.sub(r'^\d+\s*[-.]?\s*', '', cleaned).strip()
    # Strip parenthetical annotations: "(ao vivo)", "[live]", "(Part. X)"
    cleaned = re.sub(r'\s*[\(\[].*?[\)\]]', '', cleaned).strip()
    # Strip Part./Feat. participation suffixes
    cleaned = re.sub(r'\s*[-–]?\s*(part\.|feat\.|ft\.)\s*.+$', '', cleaned,
                     flags=re.IGNORECASE).strip()

    if ' - ' not in cleaned:
        return '', cleaned

    parts = [p.strip() for p in cleaned.split(' - ')]
    if len(parts) == 2:
        return parts[0], parts[1]
    # 3+ parts: "Artist - Album - Title" → use first and last
    return parts[0], parts[-1]


# ── Artist similarity ─────────────────────────────────────────────────────────

_MIN_ARTIST_SIMILARITY = 0.3


def _artist_similarity(a: str, b: str) -> float:
    """Word-overlap similarity between two artist names (0.0–1.0)."""
    if not a or not b:
        return 0.0
    norm = lambda s: set(re.sub(r'[^\w\s]', '', s.lower()).split())
    w1, w2 = norm(a), norm(b)
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / min(len(w1), len(w2))


# ── Public API ────────────────────────────────────────────────────────────────

def enrich_file(path: str, write_back: bool = True, min_score: int = _MIN_SCORE) -> dict:
    current = _read_current_tags(path)
    title   = current['title']
    artist  = current['artist']

    # Fill gaps from filename using smart parser
    if not title or not artist:
        name = os.path.splitext(os.path.basename(path))[0]
        parsed_artist, parsed_title = _parse_filename(name)
        if not title:
            title = parsed_title
        if not artist:
            artist = parsed_artist

    match = _search_musicbrainz(title, artist)
    if not match or match['score'] < min_score:
        return {
            'status':  'no_match',
            'path':    path,
            'message': 'Nenhum match encontrado com score suficiente.',
        }

    # Reject match when returned artist diverges significantly from known artist
    if artist and match.get('artist'):
        sim = _artist_similarity(artist, match['artist'])
        if sim < _MIN_ARTIST_SIMILARITY:
            return {
                'status':  'no_match',
                'path':    path,
                'message': (f"Match rejeitado: artista MusicBrainz '{match['artist']}' "
                            f"incompatível com '{artist}' (similaridade {sim:.2f})."),
            }

    cover_bytes = _fetch_cover_art(match['release_mbid']) if match.get('release_mbid') else None

    if not write_back:
        return {
            'status':     'found',
            'path':       path,
            'match':      match,
            'has_cover':  cover_bytes is not None,
            'write_back': False,
        }

    backup_entry = backup_tags(path)

    try:
        _write_tags(
            path,
            title=match['title']  or None,
            artist=match['artist'] or None,
            album=match['album']  or None,
            cover_bytes=cover_bytes,
        )
    except Exception as e:
        return {
            'status':  'error',
            'path':    path,
            'message': str(e),
            'backup':  _strip_apic(backup_entry),
        }

    return {
        'status':     'ok',
        'path':       path,
        'match':      match,
        'has_cover':  cover_bytes is not None,
        'backup':     _strip_apic(backup_entry),
        'write_back': True,
    }


def restore_file(path: str) -> dict:
    backup   = _load_backup()
    abs_path = os.path.abspath(path)
    entry    = backup.get(abs_path)
    if not entry:
        return {
            'status':  'not_found',
            'path':    path,
            'message': 'Nenhum backup encontrado para este arquivo.',
        }

    cover_bytes = None
    if entry.get('apic'):
        try:
            cover_bytes = base64.b64decode(entry['apic'])
        except Exception:
            pass

    try:
        _write_tags(
            path,
            title=entry.get('title') or None,
            artist=entry.get('artist') or None,
            album=entry.get('album') or None,
            cover_bytes=cover_bytes,
        )
    except Exception as e:
        return {'status': 'error', 'path': path, 'message': str(e)}

    del backup[abs_path]
    _save_backup(backup)
    return {'status': 'ok', 'path': path, 'restored': _strip_apic(entry)}


def list_backup() -> list[dict]:
    return [
        {
            'path':         p,
            'title':        e.get('title', ''),
            'artist':       e.get('artist', ''),
            'album':        e.get('album', ''),
            'has_apic':     bool(e.get('apic')),
            'backed_up_at': e.get('backed_up_at', ''),
        }
        for p, e in _load_backup().items()
        if not p.startswith('_')  # exclui chaves internas como _renames
    ]


def get_embedded_cover(path: str) -> tuple[bytes, str] | None:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.mp3':
            from mutagen.id3 import ID3
            tags = ID3(path)
            keys = [k for k in tags if k.startswith('APIC')]
            if keys:
                apic = tags[keys[0]]
                return (apic.data, apic.mime or 'image/jpeg')
        elif ext == '.flac':
            from mutagen.flac import FLAC
            af = FLAC(path)
            if af.pictures:
                p = af.pictures[0]
                return (p.data, p.mime or 'image/jpeg')
        elif ext == '.m4a':
            from mutagen.mp4 import MP4, MP4Cover
            af = MP4(path)
            covr = af.get('covr', [])
            if covr:
                fmt  = covr[0].imageformat
                mime = 'image/png' if fmt == MP4Cover.FORMAT_PNG else 'image/jpeg'
                return (bytes(covr[0]), mime)
        elif ext == '.ogg':
            from mutagen.oggvorbis import OggVorbis
            af = OggVorbis(path)
            blocks = af.get('metadata_block_picture', [])
            if blocks:
                from mutagen.flac import Picture
                pic = Picture(base64.b64decode(blocks[0]))
                return (pic.data, pic.mime or 'image/jpeg')
    except Exception:
        pass
    return None


def get_folder_cover(path: str) -> tuple[bytes, str] | None:
    directory = os.path.dirname(path)
    for name in ('cover.jpg', 'cover.jpeg', 'Cover.jpg', 'Cover.jpeg',
                 'folder.jpg', 'Folder.jpg', 'front.jpg', 'Front.jpg',
                 'album.jpg',  'artwork.jpg',
                 'cover.png',  'folder.png', 'front.png'):
        candidate = os.path.join(directory, name)
        if os.path.exists(candidate):
            mime = 'image/png' if candidate.lower().endswith('.png') else 'image/jpeg'
            with open(candidate, 'rb') as f:
                return (f.read(), mime)
    return None


# ── Renomeação ────────────────────────────────────────────────────────────────

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')

_PATTERNS = {
    'artist_title':       [('artist', 'Artista'), ('title', 'Título')],
    'artist_album_title': [('artist', 'Artista'), ('album', 'Álbum'), ('title', 'Título')],
}


def _sanitize(name: str) -> str:
    return _INVALID_CHARS.sub('_', name).strip('. ')


def _build_filename(tags: dict, pattern: str) -> str | None:
    fields = _PATTERNS.get(pattern, _PATTERNS['artist_title'])
    parts  = [_sanitize(tags.get(f, '')) for f, _ in fields]
    parts  = [p for p in parts if p]
    if not _sanitize(tags.get('title', '')):
        return None  # título é obrigatório
    return ' - '.join(parts) if parts else None


def rename_file(path: str, pattern: str = 'artist_title', dry_run: bool = True) -> dict:
    tags     = _read_current_tags(path)
    ext      = os.path.splitext(path)[1].lower()
    new_base = _build_filename(tags, pattern)

    if not new_base:
        return {
            'status':  'skip',
            'path':    path,
            'message': 'Título ausente nas tags — impossível renomear.',
        }

    new_name = new_base + ext
    new_path = os.path.join(os.path.dirname(path), new_name)

    if os.path.abspath(path) == os.path.abspath(new_path):
        return {
            'status':   'unchanged',
            'path':     path,
            'new_name': new_name,
            'message':  'Nome já está no padrão.',
        }

    if dry_run:
        return {
            'status':   'dry_run',
            'path':     path,
            'old_name': os.path.basename(path),
            'new_name': new_name,
        }

    if os.path.exists(new_path):
        return {
            'status':   'collision',
            'path':     path,
            'new_path': new_path,
            'message':  'Já existe um arquivo com esse nome no diretório.',
        }

    # Guarda o caminho original antes de renomear
    backup          = _load_backup()
    renames         = backup.setdefault('_renames', {})
    renames[os.path.abspath(new_path)] = os.path.abspath(path)
    _save_backup(backup)

    os.rename(path, new_path)

    return {
        'status':   'ok',
        'old_path': path,
        'new_path': new_path,
        'old_name': os.path.basename(path),
        'new_name': new_name,
    }


def restore_rename(path: str) -> dict:
    backup   = _load_backup()
    renames  = backup.get('_renames', {})
    abs_path = os.path.abspath(path)

    original = renames.get(abs_path)
    if not original:
        return {
            'status':  'not_found',
            'path':    path,
            'message': 'Nenhum rename registrado para este arquivo.',
        }

    if not os.path.exists(abs_path):
        return {'status': 'error', 'path': path, 'message': 'Arquivo não encontrado no caminho atual.'}

    if os.path.exists(original):
        return {
            'status':   'collision',
            'path':     path,
            'original': original,
            'message':  'Já existe um arquivo no caminho original.',
        }

    os.rename(abs_path, original)
    del renames[abs_path]
    backup['_renames'] = renames
    _save_backup(backup)

    return {'status': 'ok', 'restored_to': original, 'from': abs_path}


def list_renames() -> list[dict]:
    return [
        {'current_path': new, 'original_path': old}
        for new, old in _load_backup().get('_renames', {}).items()
    ]
