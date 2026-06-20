# Fontes de conteúdo

Cada fonte é configurada em `config.yaml` dentro da lista `sources`. Todo source aceita um campo `context` para orientar o roteirista — tom, foco temático, público-alvo.

---

## YouTube (`type: youtube`)

Busca vídeos recentes de canais configurados. Suporta OAuth para incluir inscrições.

```yaml
- id: youtube
  type: youtube
  name: "Vídeos do Youtube"
  enabled: true
  channels:
    - id: UCaGmdJSSiR7fkh2A-c6emsA
      name: "G1"
    - id: UC-wcdrzucnlKGBjyEUaEWaQ
      name: "Jovem Pan News"
  settings:
    max_videos_per_channel: 2    # máximo de vídeos por canal
    max_videos_total: 15         # total máximo
    days_lookback: 7             # busca vídeos dos últimos N dias
    language_preference: [pt, en]
    subscriptions_ratio: 0.6     # % de vídeos das inscrições (requer OAuth)
```

**Como ativar OAuth (inscrições do YouTube):**
1. No Google Cloud Console, crie credenciais OAuth 2.0 (Aplicativo Desktop)
2. Baixe o `client_secret.json` e coloque na raiz do projeto
3. Execute `python src/auth.py` uma vez para autenticar

---

## RSS (`type: rss`)

Lê feeds RSS de qualquer site. O Claude gera um boletim de notícias a partir dos artigos.

```yaml
- id: noticias
  type: rss
  name: "Notícias do Dia"
  enabled: true
  feeds:
    - url: "https://g1.globo.com/rss/g1/"
      name: "G1"
    - url: "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"
      name: "Folha"
  settings:
    max_items_per_feed: 2    # itens por feed
    max_items_total: 12      # total máximo
    days_lookback: 1         # ignora itens mais antigos que N dias
```

### Scraping de sites sem RSS nativo

Sites sem feed RSS podem ser usados com `scrape: true`. O sistema extrai os links da página inicial e usa o trafilatura para obter título, texto e data de cada artigo.

```yaml
  feeds:
    - url: "https://g1.globo.com/rss/g1/"
      name: "G1"
    - url: "https://prefeitura.cidade.gov.br/noticias"
      name: "Prefeitura"
      scrape: true
```

> Sem RSS, a data pode não estar disponível — o item é incluído sem filtrar por `days_lookback`.

### Feeds verificados e funcionando

| Veículo | URL |
|---------|-----|
| G1 | `https://g1.globo.com/rss/g1/` |
| Folha de São Paulo | `https://feeds.folha.uol.com.br/emcimadahora/rss091.xml` |
| Gazeta do Povo | `https://www.gazetadopovo.com.br/feed/rss/ultimas-noticias.xml` |
| Agência Brasil | `https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml` |
| CNN Brasil | `https://admin.cnnbrasil.com.br/rss` |
| Metrópoles | `https://www.metropoles.com/feed/` |
| Poder360 | `https://www.poder360.com.br/feed/` |
| TecMundo | `https://rss.tecmundo.com.br/feed` |
| Olhar Digital | `https://olhardigital.com.br/feed/` |
| Canaltech | `https://canaltech.com.br/rss/` |
| G1 São Paulo | `https://g1.globo.com/sao-paulo/rss/g1/sao-paulo.xml` |
| Google (cidade) | `https://news.google.com/rss/search?q=sua+cidade&hl=pt-BR&gl=BR` |

Para adicionar um novo feed, basta incluir na lista `feeds` de qualquer fonte `type: rss`:

```yaml
feeds:
  - url: "https://exemplo.com.br/feed"
    name: "Nome do Veículo"
```

---

## Combined (`type: combined`)

Agrega conteúdo de múltiplas fontes em um único episódio. Ideal para blocos matinais que misturam utilidades, notícias e vídeos em uma narrativa coesa.

```yaml
- id: bom-dia
  type: combined
  name: "Bom Dia"
  enabled: true
  sources:
    - utilidades
    - noticias
    - youtube
  model: "claude-haiku-4-5-20251001"
  context: "tom animado e acolhedor, foco regional"
```

O sistema chama `fetch()` de cada sub-fonte, junta o conteúdo e passa para o LLM com um prompt que incentiva conexões entre os temas.

**Restrições:**
- Sub-fontes do tipo `utility`, `music` e `spot` são ignoradas (não têm `fetch()`)
- Os IDs em `sources` devem ser fontes já existentes no `config.yaml`

---

## Utilidades (`type: utility`)

Coleta dados de APIs públicas (clima, câmbio, loteria, futebol) e gera um roteiro narrativo. Cada seção é opcional e independente.

```yaml
- id: utilidades
  type: utility
  name: "Resumo do Dia"
  enabled: true
  settings:

    weather:
      enabled: true
      cities:
        - "Sao Paulo,BR"
        - "Rio de Janeiro,BR"
      api_key_env: "OPENWEATHER_API_KEY"
      forecast_days: 3    # previsão dos próximos N dias (0 = desativado, máx 5)

    finance:
      enabled: true
      pairs:
        - "USD-BRL"
        - "EUR-BRL"
        - "BTC-USD"

    lottery:
      enabled: true
      games:
        - megasena
        - lotofacil
        - quina
        # Outras: lotomania | timemania | duplasena | diadesorte

    football:
      enabled: true
      competition: WC
      api_key_env: FOOTBALL_DATA_API_KEY
```

**Códigos de competição (football-data.org):**

| Código | Competição |
|--------|-----------|
| `WC` | FIFA World Cup |
| `BSA` | Campeonato Brasileiro Série A |
| `CL` | UEFA Champions League |
| `CLI` | Copa Libertadores |

---

## Reddit (`type: reddit`)

Busca os posts mais votados do dia em subreddits configurados.

```yaml
- id: reddit
  type: reddit
  name: "Tendências do Reddit"
  enabled: true
  subreddits:
    - brasil
    - investimentos
    - brdev
  settings:
    max_per_subreddit: 3
    max_total: 10
    timeframe: day    # hour | day | week | month | year
    min_score: 50
```

---

## Efemérides (`type: efemerides`)

Busca eventos históricos do dia na Wikipedia em português.

```yaml
- id: efemerides
  type: efemerides
  name: "Hoje na História"
  enabled: true
  settings:
    max_events: 3
    categories:
      - selected    # eventos curados pela Wikipedia (melhor qualidade)
      - events      # todos os eventos do dia
      # - births
      # - deaths
```

---

## Horóscopo (`type: horoscopo`)

Previsão do dia para dois signos do zodíaco. Os 12 signos são cobertos em 6 duplas, como nas rádios brasileiras.

```yaml
- id: horoscopo
  type: horoscopo
  name: "Horóscopo do Dia"
  enabled: true
  settings:
    # pair_index: 0   # omitir = rotação automática por dia do ano
```

| Parâmetro | Signos |
|-----------|--------|
| `horoscopo:0` | Áries e Touro |
| `horoscopo:1` | Gêmeos e Câncer |
| `horoscopo:2` | Leão e Virgem |
| `horoscopo:3` | Libra e Escorpião |
| `horoscopo:4` | Sagitário e Capricórnio |
| `horoscopo:5` | Aquário e Peixes |

---

## Quiz (`type: trivia`)

Gera um segmento de quiz com perguntas da Open Trivia Database.

```yaml
- id: quiz
  type: trivia
  name: "Quiz do Dia"
  enabled: true
  settings:
    amount: 5
    # category: 23        # ver tabela abaixo
    # difficulty: medium  # easy | medium | hard
```

| Código | Categoria |
|--------|-----------|
| 9 | Conhecimentos Gerais |
| 17 | Ciência e Natureza |
| 18 | Tecnologia |
| 21 | Esportes |
| 22 | Geografia |
| 23 | História |
| 25 | Arte |

---

## Filmes (`type: filmes`)

Busca filmes no TMDB e gera um quadro de indicações. Requer chave gratuita em themoviedb.org/settings/api.

```yaml
- id: filmes
  type: filmes
  name: "Cine Indica"
  enabled: true
  settings:
    api_key_env: TMDB_API_KEY
    mode: trending      # trending | now_playing | upcoming | top_rated
    language: pt-BR
    region: BR
    max_movies: 5
```

| Modo | Conteúdo |
|------|----------|
| `trending` | Filmes em tendência global hoje |
| `now_playing` | Em cartaz nos cinemas |
| `upcoming` | Lançamentos futuros |
| `top_rated` | Mais bem avaliados de todos os tempos |

---

## URL (`type: url`)

Gera um episódio a partir de qualquer URL — notícia, artigo, vídeo do YouTube, etc. Não requer configuração no `config.yaml`.

```bash
python main.py "url:https://exemplo.com/artigo"
python main.py "url:https://youtu.be/VIDEO_ID"
python main.py "url:https://a.com/artigo,https://b.com/artigo"   # múltiplas URLs
python main.py "url:https://exemplo.com/artigo|foca nos aspectos econômicos"
```

> URLs com `&` no PowerShell precisam de aspas duplas ao redor do argumento inteiro.

Sites renderizados via JavaScript (SPAs) podem não funcionar — trafilatura não executa JS.

---

## Receitas (`type: receitas`)

Busca uma receita culinária e gera um quadro de rádio descontraído.

**Via RSS** (padrão quando `feeds` está configurado):

```yaml
- id: receitas
  type: receitas
  name: "Receita do Dia"
  enabled: true
  settings:
    feeds:
      - url: "https://www.panelaterapia.com/feed/"
        name: "Panelaterapia"
```

**Via TheMealDB** (fallback automático, ou modo principal sem `feeds`):

```yaml
    areas:
      - Italian
      - Portuguese
      - Mexican
```

Áreas disponíveis: `American`, `British`, `Chinese`, `French`, `Greek`, `Indian`, `Italian`, `Japanese`, `Mexican`, `Portuguese`, `Spanish`, `Thai`, entre outras.

---

## Música (`type: music`)

Insere faixas musicais no episódio.

```yaml
# Jamendo (músicas licenciadas)
- id: musica
  type: music
  name: "Seleção Musical"
  enabled: false
  settings:
    num_tracks: 3
    source: "jamendo"
    cache_size: 50    # faixas a baixar por execução de download-musica
    jamendo:
      api_key_env: "JAMENDO_CLIENT_ID"
      tags: "lounge"    # lounge | jazz | ambient | pop | electronic | classical | rock
      min_duration: 60
      max_duration: 360

# Pasta local
- id: musica-local
  type: music
  name: "Playlist Local"
  enabled: false
  settings:
    num_tracks: 2
    source: "local"    # lê arquivos de music/ e subpastas
```

Para popular o cache do Jamendo sem gerar episódio:

```bash
python main.py download-musica
```

---

## Clipping (`type: clipping`)

Panorama de como a mídia está cobrindo um tema. O tópico é sempre passado junto com o ID:

```bash
python main.py "clipping:reforma tributaria 2026"
```

No Admin UI: selecione Clipping e preencha o campo de contexto com o tema.

```yaml
- id: clipping
  type: clipping
  name: "Clipping"
  enabled: true
  settings:
    max_sources: 5
    days_lookback: 1
    fetch_content: true
    max_content_chars: 2000
    agregadores:
      - google_news
      - bing_news
```

---

## Clipping Automático (`type: clipping_auto`)

Descobre o assunto mais discutido do dia via RSS + LLM e gera o clipping automaticamente.

```yaml
- id: clipping-geral
  type: clipping_auto
  name: "Clipping do Dia"
  enabled: true
  settings:
    max_topics: 3
    max_sources: 5
    days_lookback: 1
    llm_model: claude-haiku-4-5-20251001
    topic_history_days: 7       # evita repetir assunto dos últimos N dias
    topic_cooldown_hours: 4     # evita repetir o mesmo assunto dentro de N horas
    categoria: política         # filtra o LLM para um tema (opcional)
    agregadores:
      - google_news
      - bing_news
    trending_feeds:
      - https://g1.globo.com/rss/g1/
      - https://feeds.folha.uol.com.br/emcimadahora/rss091.xml
```

Configure instâncias com categorias distintas para uma grade completa de clipping:

```bash
python main.py clipping-politica clipping-economia clipping-esportes
```

---

## Plugins incluídos

| Plugin | `type` | Descrição |
|--------|--------|-----------|
| `biblia.py` | `biblia` | Passagens bíblicas (ABíbliaDigital) — token gratuito em `ABIBLIADIGITAL_TOKEN` |
| `podcast.py` | `podcast` | Episódio a partir de feed RSS de podcast ou MP3 direto |
| `whatsapp.py` | `whatsapp` | Resumo de grupo do WhatsApp a partir de exportação manual |
| `concursos_pci.py` | `concursos_pci` | Notícias de concursos públicos (PCI Concursos) |

Para criar novos plugins, consulte: [docs/criando-geradores.md](criando-geradores.md)
