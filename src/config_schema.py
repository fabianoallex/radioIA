"""Validação do config.yaml com Pydantic v2.

Chamado em load_config() de main.py, mcp_server.py e scheduler.py.
ConfigError é levantado para erros fatais (bloqueiam a execução).
Avisos são impressos mas não bloqueiam.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ConfigError(Exception):
    pass


# ── Sub-modelos ──────────────────────────────────────────────────────────────

class NarratorConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str
    voice: str
    personality: str


class RadioConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str


class ScheduleEntry(BaseModel):
    model_config = ConfigDict(extra='allow')
    time: Any
    label: str = ''

    @field_validator('time', mode='before')
    @classmethod
    def normalise_time(cls, v: Any) -> str:
        if isinstance(v, int):
            v = f"{v // 60:02d}:{v % 60:02d}"
        s = str(v)
        if not re.match(r'^\d{2}:\d{2}$', s):
            raise ValueError(f"formato inválido '{s}' — esperado HH:MM")
        return s

    @model_validator(mode='before')
    @classmethod
    def has_sources_or_replay(cls, data: dict) -> dict:
        if 'sources' not in data and 'replay_of' not in data:
            raise ValueError("precisa de 'sources' ou 'replay_of'")
        return data


# ── Campos obrigatórios por type de fonte ────────────────────────────────────

_SOURCE_REQUIRED_FIELDS: dict[str, list[str]] = {
    'combined': ['sources'],
    'rss':      ['feeds'],
    'youtube':  ['channels'],
}


# ── Validadores individuais ──────────────────────────────────────────────────

def _validate_sources(sources: list[dict]) -> list[str]:
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for i, source in enumerate(sources):
        loc = f"sources[{i}]"

        for field in ('id', 'type', 'name'):
            if not source.get(field):
                raise ConfigError(f"{loc}: campo obrigatório '{field}' ausente ou vazio")

        sid   = source['id']
        stype = source['type']

        if sid in seen_ids:
            raise ConfigError(f"sources: ID duplicado '{sid}'")
        seen_ids.add(sid)

        if not source.get('enabled', True):
            continue

        required = _SOURCE_REQUIRED_FIELDS.get(stype, [])
        for field in required:
            val = source.get(field)
            if val is None:
                raise ConfigError(
                    f"sources['{sid}'] (type: {stype}): "
                    f"campo '{field}' ausente — obrigatório para este tipo"
                )
            if isinstance(val, list) and len(val) == 0:
                warnings.append(
                    f"  [aviso config] sources['{sid}']: '{field}' está vazio"
                )

    return warnings


def _pydantic_msg(exc: Exception) -> str:
    from pydantic import ValidationError
    if not isinstance(exc, ValidationError):
        return str(exc)
    parts = []
    for err in exc.errors():
        field = '.'.join(str(l) for l in err.get('loc', ())) or '(entrada)'
        msg   = err.get('msg', str(err))
        parts.append(f"{field}: {msg}")
    return '; '.join(parts)


def _validate_narrators(narrators: list) -> list[str]:
    errors: list[str] = []
    if not narrators:
        errors.append("narrators: configure ao menos um narrador")
        return errors
    for i, n in enumerate(narrators):
        try:
            NarratorConfig(**n)
        except Exception as e:
            errors.append(f"narrators[{i}]: {_pydantic_msg(e)}")
    return errors


def _validate_schedule(schedule: list) -> list[str]:
    errors: list[str] = []
    for i, entry in enumerate(schedule):
        try:
            ScheduleEntry(**entry)
        except Exception as e:
            label = entry.get('label', '')
            time  = entry.get('time', '')
            errors.append(f"schedule[{i}] ('{label}' {time}): {_pydantic_msg(e)}")
    return errors


# ── Ponto de entrada ─────────────────────────────────────────────────────────

def validate_config(raw: dict) -> None:
    """
    Valida o config carregado do YAML.
    Levanta ConfigError com lista de todos os problemas encontrados.
    Imprime avisos não-bloqueadores antes de retornar.
    """
    errors:   list[str] = []
    warnings: list[str] = []

    # radio.name
    radio = raw.get('radio') or {}
    if not isinstance(radio, dict) or not radio.get('name'):
        errors.append("radio.name é obrigatório")

    # narrators
    errors.extend(_validate_narrators(raw.get('narrators') or []))

    # sources
    sources = raw.get('sources') or []
    try:
        warnings.extend(_validate_sources(sources))
    except ConfigError as e:
        errors.append(str(e))

    # schedule
    errors.extend(_validate_schedule(raw.get('schedule') or []))

    for w in warnings:
        print(w)

    if errors:
        bullet = '\n'.join(f'  • {e}' for e in errors)
        raise ConfigError(f'\n[config.yaml] Erros de configuração:\n{bullet}\n')
