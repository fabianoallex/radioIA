"""
Exemplo de plugin RadioIA — Frase do Dia

Demonstra o contrato mínimo para um gerador de episódio.
Remova ou renomeie este arquivo para desativá-lo.

Para usar, adicione ao config.yaml:
  - id: frase-do-dia
    type: exemplo_plugin
    name: "Frase do Dia"
    enabled: true
    settings:
      categoria: motivacional   # motivacional | filosofia | humor
"""

import random
from datetime import date

FRASES = {
    'motivacional': [
        ("Nada é impossível para quem tenta.", "Adaptado de Alexandre, o Grande"),
        ("O sucesso é a soma de pequenos esforços repetidos dia após dia.", "Robert Collier"),
        ("Acredite que você pode e você já está na metade do caminho.", "Theodore Roosevelt"),
    ],
    'filosofia': [
        ("Conhece-te a ti mesmo.", "Sócrates"),
        ("Só sei que nada sei.", "Sócrates"),
        ("O homem é a medida de todas as coisas.", "Protágoras"),
    ],
    'humor': [
        ("Nunca adie o que você pode fazer depois de amanhã.", "Mark Twain"),
        ("Não ponha para amanhã o que você pode esquecer para sempre.", "Anônimo"),
        ("A vida é curta demais para acordar de manhã com arrependimentos.", "Anônimo"),
    ],
}


def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings  = source_config.get('settings') or {}
    categoria = settings.get('categoria', 'motivacional')
    frases    = FRASES.get(categoria, FRASES['motivacional'])
    frase, autor = random.choice(frases)
    today = date.today().isoformat()

    print(f"  Frase: \"{frase}\" — {autor}")

    return [{
        'id':           f"frase-{abs(hash(frase)) % 10**6}-{today}",
        'title':        frase,
        'url':          '',
        'text':         f'"{frase}" — {autor}',
        'source_name':  source_config.get('name', 'Frase do Dia'),
        'source_type':  source_config.get('type', 'exemplo_plugin'),
        'published_at': today,
        'views':        0,
        'comments':     [],
        'channel':      categoria.capitalize(),
    }]
