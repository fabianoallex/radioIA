# Criando geradores de episódio

Um gerador é um arquivo Python que busca conteúdo de qualquer fonte e o entrega ao RadioIA para virar roteiro e áudio. Qualquer pessoa pode criar e compartilhar geradores sem modificar o projeto principal.

---

## Como funciona

O RadioIA carrega automaticamente todos os arquivos `.py` da pasta `plugins/` ao iniciar. Cada arquivo é um gerador independente identificado pelo nome do arquivo.

```
radioIA/
  plugins/
    meu_gerador.py      ← carregado automaticamente
    outro_gerador.py    ← carregado automaticamente
    _rascunho.py        ← ignorado (começa com _)
```

---

## O contrato

Todo gerador precisa implementar uma única função:

```python
def fetch(source_config: dict, credentials=None) -> list[dict]:
    ...
```

### Parâmetros

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `source_config` | `dict` | Configuração completa do source no `config.yaml` |
| `credentials` | `object` | Credenciais OAuth do YouTube (raramente necessário) |

`source_config` contém tudo que foi definido no `config.yaml` para este source:
```python
source_config = {
    'id':       'meu-gerador',
    'type':     'meu_gerador',    # nome do arquivo .py (sem extensão)
    'name':     'Meu Gerador',
    'enabled':  True,
    'settings': { ... }           # campos personalizados
}
```

### Retorno

A função deve retornar uma `list[dict]`. Cada dict representa um item de conteúdo:

```python
{
    # ── Obrigatórios ──────────────────────────────────────────
    'id':           'identificador-unico-do-item',  # usado para deduplicação
    'title':        'Título do conteúdo',
    'text':         'Texto completo que o Claude vai narrar',
    'source_type':  'meu_gerador',                  # mesmo que o type no config.yaml

    # ── Recomendados ──────────────────────────────────────────
    'url':          'https://link-da-fonte.com',    # link de referência ('' se não houver)
    'source_name':  'Nome da Fonte',                # exibido no player
    'published_at': '2026-06-04',                   # data de publicação (YYYY-MM-DD)
    'channel':      'Categoria ou Seção',           # exibido no player

    # ── Opcionais ─────────────────────────────────────────────
    'views':        1500,                           # visualizações/votos (0 se não aplicável)
    'comments':     [],                             # lista de comentários (raramente usada)
}
```

**Retorne lista vazia `[]` se não houver conteúdo disponível** — o RadioIA pula o gerador silenciosamente.

---

## Exemplo mínimo

```python
# plugins/clima_simples.py
import requests
from datetime import date

def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings = source_config.get('settings') or {}
    cidade   = settings.get('cidade', 'Cuiabá')

    try:
        resp = requests.get(
            'https://wttr.in/' + cidade,
            params={'format': '%C+%t'},
            timeout=10
        )
        descricao = resp.text.strip()
    except Exception as e:
        print(f"  [clima_simples] {e}")
        return []

    return [{
        'id':           f"clima-{cidade}-{date.today()}",
        'title':        f"Clima em {cidade}",
        'url':          f"https://wttr.in/{cidade}",
        'text':         f"Agora em {cidade}: {descricao}.",
        'source_name':  source_config.get('name', 'Clima'),
        'source_type':  'clima_simples',
        'published_at': date.today().isoformat(),
        'views':        0,
        'comments':     [],
        'channel':      cidade,
    }]
```

---

## Registrar no config.yaml

Após criar o arquivo em `plugins/`, adicione o source ao `config.yaml`:

```yaml
sources:
  - id: clima-cuiaba
    type: clima_simples        # nome do arquivo .py sem extensão
    name: "Clima de Cuiabá"
    enabled: true
    settings:
      cidade: "Cuiabá"
```

E na grade de programação:

```yaml
schedule:
  - time: "07:15"
    label: "Clima"
    sources: [clima-cuiaba]
```

---

## Testar

```bash
python main.py clima-cuiaba
```

O RadioIA carrega o plugin, busca o conteúdo, gera o roteiro com Claude e produz o episódio MP3.

---

## Boas práticas

**`id` único e estável** — inclua a data e algo específico do conteúdo. O RadioIA usa o `id` para não repetir itens já veiculados.

```python
'id': f"clima-{cidade}-{date.today().isoformat()}"
```

**Trate exceções** — sempre envolva chamadas de rede em `try/except` e retorne `[]` em caso de falha. O RadioIA não deve cair por causa de um plugin.

**Use `settings`** — parâmetros que o usuário pode configurar no `config.yaml` devem vir de `source_config.get('settings') or {}`, nunca hardcoded.

**Imprima progresso** — use `print(f"  [nome] ...")` para feedback no terminal durante a geração.

**Não dependa de estado global** — `fetch()` pode ser chamada várias vezes por dia. Cada chamada deve ser independente.

---

## Dependências externas

Se o plugin precisar de pacotes não incluídos no `requirements.txt`, documente no início do arquivo:

```python
"""
Dependências: pip install spotipy
"""
import spotipy
```

---

## Compartilhar com outros devs

Basta subir o arquivo `.py` no GitHub (repositório próprio, Gist, ou PR para um repositório comunitário). Quem quiser usar faz o download e coloca em `plugins/`.

O arquivo é totalmente autossuficiente — desde que respeite o contrato `fetch()`, funciona em qualquer instalação do RadioIA.

---

## Referência rápida

```python
def fetch(source_config: dict, credentials=None) -> list[dict]:
    settings = source_config.get('settings') or {}

    # ... busca conteúdo ...

    return [{
        'id':           'unico-por-item-e-data',   # obrigatório
        'title':        'Título',                  # obrigatório
        'text':         'Texto para o Claude',     # obrigatório
        'source_type':  'nome_do_arquivo',         # obrigatório
        'url':          '',                        # recomendado
        'source_name':  'Nome',                    # recomendado
        'published_at': '2026-06-04',              # recomendado
        'channel':      'Categoria',               # recomendado
        'views':        0,                         # opcional
        'comments':     [],                        # opcional
    }]
```
