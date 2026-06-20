# Servidor MCP

O `mcp_server.py` expõe a RadioIA como um servidor [MCP (Model Context Protocol)](https://modelcontextprotocol.io), permitindo que agentes de IA operem a rádio completamente por conversa.

---

## Iniciar

```bash
python mcp_server.py
```

---

## Configurar no Claude Code

`~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "radioIA": {
      "command": "python",
      "args": ["C:/caminho/para/radioIA/mcp_server.py"]
    }
  }
}
```

Após configurar, você pode pedir ao Claude:
- *"Gera um episódio de notícias e copa do mundo"*
- *"Faz um clipping sobre a reforma tributária"*
- *"Inicia o scheduler"* / *"Para o scheduler"*
- *"Habilita a fonte de música e adiciona um bloco musical às 12h"*
- *"Remove episódios mais antigos que 14 dias"*

---

## Ferramentas disponíveis

### Geração de conteúdo

| Ferramenta | Descrição |
|-----------|-----------|
| `gerar_episodios(["noticias", "copa"])` | Gera episódios para as fontes especificadas |
| `gerar_episodios(["musica:3"])` | Gera bloco musical com N faixas |
| `gerar_episodios(["url:https://..."])` | Gera episódio a partir de URL |
| `gerar_episodios(["noticias\|foca em economia"])` | Com instrução de foco para o roteirista |
| `gerar_episodios(["noticias"], model="claude-haiku-4-5-20251001")` | Override de modelo |
| `gerar_clipping("reforma tributária 2026")` | Clipping sobre um tema específico |
| `gerar_clipping("copa", followup=True)` | Clipping de acompanhamento — só artigos recentes |
| `gerar_clipping("tema", agregadores=["bing_news"])` | Clipping com agregador específico |
| `gerar_clipping_automatico()` | Descobre e clipa o assunto mais discutido do dia |
| `gerar_clipping_automatico(categoria="economia")` | Clipping automático filtrado por tema |
| `gerar_podcast("https://feed.rss")` | Episódio a partir de feed RSS ou MP3 de podcast |
| `deletar_episodio("09-30_youtube")` | Remove a pasta de um episódio |
| `replay_episodio("12-15_not")` | Replay de episódio por prefixo da pasta |
| `replay_episodio("12-15", "2026-06-03")` | Replay de episódio de outra data |

### Consulta

| Ferramenta | Descrição |
|-----------|-----------|
| `listar_episodios()` | Lista episódios gerados hoje |
| `listar_episodios("2026-06-10")` | Lista episódios de uma data específica |
| `ler_episodio("2026-06-15", "noticias")` | Roteiro completo e metadados |
| `listar_fontes()` | Fontes configuradas com tipo, status e histórico |
| `listar_modelos()` | Modelos LLM disponíveis e modelo padrão |
| `status_historico()` | Itens já citados e total de episódios gerados |
| `status_geracao()` | Estado da geração em andamento |
| `listar_assuntos()` | Principais assuntos do momento para clipping manual |
| `listar_assuntos("economia")` | Assuntos filtrados por categoria |
| `ver_historico_clipping_auto()` | Tópicos cobertos pelo clipping automático |
| `briefing()` | Snapshot operacional completo |

### Grade e configuração

| Ferramenta | Descrição |
|-----------|-----------|
| `adicionar_fonte("bom-dia", "combined", "Bom Dia", '{"sources":["noticias","youtube"]}')` | Cria nova fonte no config.yaml |
| `configurar_fonte("musica", "enabled", "true")` | Habilita, desabilita ou altera um campo |
| `atualizar_config("radio.name", "Minha Rádio")` | Altera qualquer valor via notação de ponto |
| `ler_config()` | Lê a configuração completa |
| `ler_config("llm")` | Lê uma seção específica |
| `adicionar_grade("16:00", ["noticias"], "Tarde")` | Adiciona entrada na grade |
| `ver_grade()` | Lista a grade com status de execução |
| `remover_grade("16:00", "Tarde")` | Remove entrada da grade |
| `configurar_intro_boas_vindas(falas=[...])` | Atualiza frases da intro de boas-vindas |
| `regenerar_intro_boas_vindas()` | Regera o áudio da intro |
| `limpar_historico()` | Reseta o histórico de conteúdos veiculados |

> **Atenção:** ferramentas que salvam o `config.yaml` reformatam o arquivo YAML e perdem os comentários originais. O conteúdo e os valores são preservados.

### Scheduler

| Ferramenta | Descrição |
|-----------|-----------|
| `controlar_scheduler("status")` | Verifica se o scheduler está rodando |
| `controlar_scheduler("start")` | Inicia em background (logs em `scheduler.log`) |
| `controlar_scheduler("stop")` | Encerra pelo PID salvo |
| `ler_log()` | Últimas 50 linhas do scheduler.log |

### Sistema e manutenção

| Ferramenta | Descrição |
|-----------|-----------|
| `status_sistema()` | Status geral: scheduler, player, API keys, disco, histórico |
| `status_player()` | Estado do player: episódios de hoje e próximo agendado |
| `limpar_output(dias_manter=7)` | Lista ou remove episódios antigos |
| `testar_tts("Bem-vindos!")` | Gera `output/tts_test.mp3` para testar TTS |
| `ver_cache_jamendo()` | Cache local do Jamendo: faixas e tamanho em disco |
| `baixar_musicas_jamendo()` | Baixa novas faixas do Jamendo para o cache |
| `limpar_cache_jamendo(confirmar)` | Remove todo o cache Jamendo |

### Spots

| Ferramenta | Descrição |
|-----------|-----------|
| `adicionar_spot("aviso", "tts", texto="Atenção: reunião às 15h.")` | Spot TTS |
| `adicionar_spot("promo", "llm", topico="Promova o produto X em 20s")` | Spot LLM |
| `adicionar_spot("jingle", "file", path="spots/jingle.mp3", peso=2)` | Spot de arquivo |
| `remover_spot("aviso")` | Remove o spot do config.yaml |
| `gerar_spot("promo")` | Pré-gera o áudio cacheado |
| `gerar_spot("promo", forcar=True)` | Regenera o cache |
| `deletar_cache_spot("aviso")` | Apaga o áudio cacheado |
| `deletar_cache_spot("*")` | Limpa o cache de todos os spots |

### Exportação

| Ferramenta | Descrição |
|-----------|-----------|
| `exportar_episodios("listar")` | Lista episódios disponíveis |
| `exportar_episodios("concat")` | MP3 único do dia — salvo em `output/_exports/` |
| `exportar_episodios("zip", "2026-06-10")` | ZIP de uma data específica |
| `exportar_episodios("concat", pastas=["09-00_noticias"])` | Seleção manual |

### Operação

| Ferramenta | Descrição |
|-----------|-----------|
| `registrar_nota("observacao", "quirk")` | Persiste nota em `OPERACAO.md`, lida pelo `briefing()` |
