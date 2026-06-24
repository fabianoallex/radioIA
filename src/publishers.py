"""
Publishers — entrega o MP3 gerado para destinos externos após cada episódio.

Tipos suportados:
  local  — copia para diretório local (servido por nginx, apache, SMB, etc.)
  ftp    — envia via FTP para servidor remoto

Configuração em config.yaml:

  publishers:
    - type: local
      path: /var/www/radio/
      filename: "latest.mp3"           # sobrescreve sempre — player aponta para URL fixa

    - type: ftp
      host: ftp.empresa.com
      port: 21                          # opcional, default 21
      path: /wp-content/uploads/{YYYY}/{MM}/
      filename: "{DDMMYYYY}.mp3"        # padrão LAR: 23062026.mp3
      user_env: FTP_USER
      password_env: FTP_PASSWORD
      passive: true                     # modo passivo, default true

Tokens suportados nos campos `filename` e `path`:
  {DDMMYYYY}   → 23062026
  {YYYYMMDD}   → 20260623
  {YYYY-MM-DD} → 2026-06-23
  {YYYY}       → 2026
  {MM}         → 06
  {DD}         → 23
  {HH}         → 14
  {MIN}        → 30
  {source_id}  → id da fonte (copa, youtube, noticias…)

Para desativar publishers em uma fonte específica, adicione no config da fonte:
  external_publish: false
"""

import ftplib
import os
import shutil
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))


def _fmt(pattern: str, source_id: str, now: datetime) -> str:
    return (
        pattern
        .replace('{DDMMYYYY}',   now.strftime('%d%m%Y'))
        .replace('{YYYYMMDD}',   now.strftime('%Y%m%d'))
        .replace('{YYYY-MM-DD}', now.strftime('%Y-%m-%d'))
        .replace('{YYYY}',       now.strftime('%Y'))
        .replace('{MM}',         now.strftime('%m'))
        .replace('{DD}',         now.strftime('%d'))
        .replace('{HH}',         now.strftime('%H'))
        .replace('{MIN}',        now.strftime('%M'))
        .replace('{source_id}',  source_id)
    )


def _publish_local(episode_path: str, cfg: dict, filename: str) -> None:
    dest_dir = cfg.get('path', '').strip()
    if not dest_dir:
        raise ValueError("campo 'path' ausente ou vazio")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, filename)
    shutil.copy2(episode_path, dest)
    print(f"  [publisher/local] → {dest}")


def _publish_ftp(episode_path: str, cfg: dict, filename: str, remote_path: str) -> None:
    host     = cfg.get('host', '').strip()
    port     = int(cfg.get('port', 21))
    passive  = bool(cfg.get('passive', True))
    user     = os.getenv(cfg.get('user_env', ''), '') or cfg.get('user', 'anonymous')
    password = os.getenv(cfg.get('password_env', ''), '') or cfg.get('password', '')

    if not host:
        raise ValueError("campo 'host' ausente ou vazio")

    with ftplib.FTP() as ftp:
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        ftp.set_pasv(passive)

        for part in [p for p in remote_path.replace('\\', '/').split('/') if p]:
            try:
                ftp.cwd(part)
            except ftplib.error_perm:
                ftp.mkd(part)
                ftp.cwd(part)

        with open(episode_path, 'rb') as f:
            ftp.storbinary(f'STOR {filename}', f)

    display_path = remote_path if remote_path.endswith('/') else remote_path + '/'
    print(f"  [publisher/ftp] → ftp://{host}{display_path}{filename}")


def run_publishers(episode_path: str, publishers_config: list[dict],
                   source_id: str = '') -> None:
    """Executa todos os publishers configurados para o episódio gerado."""
    if not publishers_config:
        return
    if not episode_path or not os.path.exists(episode_path):
        print(f"  [publishers] arquivo não encontrado: {episode_path}")
        return

    now = datetime.now(BRT)

    for cfg in publishers_config:
        pub_type = cfg.get('type', '').strip()
        filename = _fmt(cfg.get('filename', 'latest.mp3'), source_id, now)

        try:
            if pub_type == 'local':
                _publish_local(episode_path, cfg, filename)

            elif pub_type == 'ftp':
                remote_path = _fmt(cfg.get('path', '/'), source_id, now)
                if not remote_path.endswith('/'):
                    remote_path += '/'
                _publish_ftp(episode_path, cfg, filename, remote_path)

            else:
                print(f"  [publisher] tipo desconhecido: '{pub_type}' — ignorado")

        except Exception as e:
            print(f"  [publisher/{pub_type}] Erro: {e}")
