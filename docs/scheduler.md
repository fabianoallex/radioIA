# Programação automática (Scheduler)

O scheduler executa fontes em horários definidos no `config.yaml`, sem intervenção manual.

---

## Comandos

```bash
python scheduler.py           # inicia o agendador
python scheduler.py --list    # exibe a grade sem rodar
pythonw scheduler.py          # inicia sem janela de terminal (Windows)
```

O scheduler recarrega o `config.yaml` a cada verificação — editar a grade não exige reiniciar.

O estado das execuções é salvo em `scheduler_state.json`:
- Entradas **diárias** são marcadas como executadas no dia e resetam à meia-noite
- Entradas **pontuais** são marcadas como concluídas permanentemente após rodar

---

## Configurar a grade

No `config.yaml`, adicione a seção `schedule`:

```yaml
schedule:
  # Diário — roda todo dia no horário indicado
  - time: "07:00"
    label: "Manhã"
    sources: [utilidades, noticias-locais]

  - time: "09:00"
    label: "Notícias"
    sources: [noticias, tecnologia]

  # Pontual — roda uma única vez na data indicada
  - time: "11:00"
    date: "2026-06-11"
    label: "Abertura da Copa"
    sources: [copa]
```

---

## Filtro por dia da semana (`days`)

O campo `days` limita a execução a dias específicos. Sem `days`, a entrada roda todo dia.

```yaml
schedule:
  - time: "09:00"
    label: "Notícias da Semana"
    sources: [noticias, tecnologia]
    days: [mon, tue, wed, thu, fri]

  - time: "09:00"
    label: "Fim de Semana"
    sources: [musica, receitas]
    days: [sat, sun]
```

**Abreviações:** `mon` `tue` `wed` `thu` `fri` `sat` `sun`

---

## Replay de episódios (`slot_id` / `replay_of`)

Reutiliza um episódio já gerado em outro horário, sem nova chamada à API. Útil para conteúdos que não mudam ao longo do dia (filmes, horóscopo, etc.).

**Como funciona:**
1. Marque o slot gerador com `slot_id: <número>`
2. Nos slots de replay, use `replay_of: <número>` no lugar de `sources`
3. O scheduler cria uma pasta de replay na hora marcada, apontando para o áudio original

```yaml
schedule:
  - time: "08:00"
    slot_id: 10
    label: "Cine Indica Manhã"
    sources: [filmes]

  - time: "14:00"
    replay_of: 10
    label: "Cine Indica (tarde)"

  - time: "16:00"
    replay_of: 10
    label: "Cine Indica (noite)"
```

> Se `replay_of` chegar antes do episódio original ser gerado, o scheduler avisa e pula.

A grade exibe `[slot:10]` nas entradas geradoras e `replay:10` nas de replay.

---

## Replay ad-hoc (fora da grade)

Para repetir um episódio agora, sem a grade:

```bash
python main.py replay:12-15              # tudo gerado às 12:15
python main.py replay:12-15_noticias    # episódio específico das 12:15
python main.py replay:noticias          # qualquer episódio de noticias do dia
```

O replay não copia o MP3 — cria apenas um `episode.json` apontando para o original.

---

## Controle via MCP

```python
controlar_scheduler("status")   # verifica se está rodando (via PID real)
controlar_scheduler("start")    # inicia em background (logs em scheduler.log)
controlar_scheduler("stop")     # encerra pelo PID salvo
ler_log()                        # últimas 50 linhas do scheduler.log
ler_log(200)                     # últimas N linhas
ver_grade()                      # lista a grade com status de execução
adicionar_grade("16:00", ["noticias"], "Tarde")
remover_grade("16:00", "Tarde")
```

O scheduler protege contra instâncias duplicadas — tentar iniciar uma segunda resulta em erro com o PID da instância já ativa.
