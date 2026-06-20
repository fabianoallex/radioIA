# Spots (propagandas e comunicados)

Spots são clipes de áudio curtos injetados automaticamente durante a programação.

---

## Tipos

| Tipo | Descrição | Quando usar |
|------|-----------|-------------|
| `file` | MP3 pré-gravado | Áudio produzido externamente |
| `tts` | Texto convertido em voz | Comunicados rápidos com a voz da rádio |
| `llm` | Tema → LLM → voz (script gerado diariamente) | Conteúdo variado sem esforço de produção |

---

## Configuração

```yaml
spots:
  - id: promo-evento
    type: file
    path: "spots/evento.mp3"
    weight: 2          # toca 2× mais que os outros (padrão: 1)
    max_per_day: 5     # limite por ouvinte por dia

  - id: aviso-reuniao
    type: tts
    text: "Atenção colaboradores: reunião geral às 15h na sala principal."
    # voice: "pt-BR-AntonioNeural"   # opcional — usa vinheta.voice se omitido

  - id: chamada-produto
    type: llm
    topic: "Promova o produto XYZ de forma descontraída em 20 segundos"
    duration_seconds: 20
    max_per_day: 3
    # model: "claude-haiku-4-5-20251001"   # opcional — usa llm.model se omitido
```

---

## Pontos de injeção

```yaml
spots_config:
  fallback_every: 5            # a cada N músicas no modo fallback (0 = desativado)
  between_episodes_every: 3   # a cada N transições entre episódios (0 = desativado)
```

Com `between_episodes_every: 3`: ep.1 → ep.2 → ep.3 → **break** → ep.4 → ep.5 → ep.6 → **break** → ...

Quando spot e anúncio de grade disparam no mesmo break, a ordem é: **spot → anúncio → próximo episódio/música**.

---

## Rotação e limites

- **`weight`** — frequência relativa entre spots (processada no servidor)
- **`max_per_day`** — limite de reproduções por ouvinte por dia (via `localStorage` no browser)
- Nunca repete o mesmo spot duas vezes consecutivas

---

## Spot como fonte agendável

Para inserir um spot em horário fixo na grade (aparece na playlist do player):

```yaml
sources:
  - id: comunicado
    type: spot
    name: "Comunicado"
    enabled: true

schedule:
  - time: "10:00"
    sources: [comunicado]
```

---

## Cache de áudio

| Tipo | Comportamento |
|------|--------------|
| `file` | Lido do disco a cada uso |
| `tts` | Gerado uma vez e salvo em `output/_spots/{id}.mp3` |
| `llm` | Gerado uma vez por dia em `output/_spots/{id}-{data}.mp3`; script em `.txt` no mesmo diretório |

---

## Gerenciar via MCP

```python
adicionar_spot("aviso", "tts", texto="Atenção: reunião às 15h.")
adicionar_spot("promo", "llm", topico="Promova o produto X em 20s", max_por_dia=3)
adicionar_spot("jingle", "file", path="spots/jingle.mp3", peso=2)
remover_spot("aviso")
gerar_spot("promo")               # pré-gera o áudio cacheado
gerar_spot("promo", forcar=True)  # regenera mesmo que já exista
deletar_cache_spot("aviso")       # força regeneração na próxima reprodução
deletar_cache_spot("*")           # limpa o cache de todos
listar_spots()                    # lista com tipo, peso e status do cache
```
