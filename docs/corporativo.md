# Rádio Corporativa

O RadioIA pode ser adaptado como **rádio interna de empresa** — veiculando comunicados, resultados, agenda e cultura organizacional de forma automática, sem equipe de rádio dedicada.

Para dar a identidade da empresa à rádio, basta editar `radio.name` no `config.yaml`. O nome se propaga automaticamente para roteiros narrados, vinhetas, tags MP3 e interface web.

---

## Conteúdos e como implementar

| Conteúdo | Como implementar |
|----------|-----------------|
| Notícias do setor | `type: rss` apontando para feeds do segmento (agro, varejo, saúde...) |
| Cotações relevantes | `type: utility` — adicionar pares de câmbio ou tickers em `finance.pairs` |
| Resultados esportivos | `type: utility` com `football` ou estender para outros esportes |
| Quiz de capacitação | `type: trivia` com banco de perguntas (Open Trivia DB ou API interna) |
| Curiosidades históricas | `type: efemerides` adaptado para uma base interna |
| Música ambiente | `type: music` com `source: local` e músicas licenciadas da empresa |
| Comunicados internos | Novo módulo `type: comunicados` lendo de SharePoint, intranet ou e-mail via API |
| KPIs e metas | Novo módulo `type: kpis` integrando com BI (Power BI, Metabase) ou ERP via API REST |
| Cardápio do refeitório | Novo módulo `type: cardapio` lendo de planilha ou sistema próprio |
| Aniversários e boas-vindas | Novo módulo `type: pessoas` integrando com AD, TOTVS ou HR system |
| Vagas internas | Novo módulo `type: vagas` lendo de ATS interno (Gupy, Workday, etc.) |
| Reconhecimentos de equipe | Módulo alimentado por formulário (Google Forms → Sheets → RSS) |

---

## Arquitetura para módulos customizados

O sistema é modular por design: cada fonte de conteúdo é um arquivo Python em `plugins/`. Para criar um novo módulo, implemente a função `fetch()`:

```python
def fetch(source_config: dict, credentials: dict) -> list[dict]:
    ...
    return [{
        'id':           'identificador-unico',
        'title':        'Título do conteúdo',
        'url':          'https://...',
        'text':         'Texto completo que o Claude vai narrar...',
        'source_name':  'Nome da Fonte',
        'source_type':  'tipo_do_modulo',
        'published_at': '2026-06-02',
        'views':        0,
        'comments':     [],
        'channel':      'Setor ou Categoria',
    }]
```

O roteador em `main.py` e o gerador em `script_generator.py` cuidam do resto. Consulte o contrato completo em [docs/criando-geradores.md](criando-geradores.md).

---

## Considerações para implantação

- **Privacidade:** conteúdos internos sensíveis não devem passar pela API da Anthropic sem avaliação jurídica. Considere usar Ollama + LLaMA localmente.
- **Infraestrutura:** o sistema roda em qualquer máquina Windows/Linux/macOS com Python. Para uso contínuo, rode o `scheduler.py` como serviço (systemd no Linux, Task Scheduler no Windows).
- **Player:** o `serve.py` é acessível por qualquer dispositivo na rede local via `http://<IP-do-servidor>:5000`, sem instalação nos clientes.
- **Vozes offline:** o Edge TTS requer conexão com a internet. Para ambientes offline, substitua por um motor TTS local (ex: Coqui TTS).
