# Modelo de linguagem (LLM)

O RadioIA usa [LiteLLM](https://github.com/BerriAI/litellm) para gerar roteiros, o que permite usar qualquer provedor de LLM sem alterar o código.

---

## Configuração global

```yaml
llm:
  model: "claude-sonnet-4-6"   # padrão para todas as fontes
```

---

## Provedores suportados

| Provedor | Exemplo de model | Chave no `.env` |
|----------|-----------------|-----------------|
| **Anthropic** (padrão) | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| **Google Gemini** | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| **Groq** (rápido e gratuito) | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| **Ollama** (local, sem custo) | `ollama/llama3.2` | — |

Para Ollama, adicione também o endpoint:

```yaml
llm:
  model: "ollama/llama3.2"
  api_base: "http://localhost:11434"
```

> **Privacidade corporativa:** para conteúdos internos sensíveis, use Ollama — nenhum dado é enviado para APIs externas.

---

## Quando usar cada modelo (Anthropic)

| Modelo | Custo relativo | Quando usar |
|--------|---------------|-------------|
| `claude-haiku-4-5-20251001` | ~10× mais barato | Fontes com estrutura rígida: `horoscopo`, `trivia`, `receitas` |
| `claude-sonnet-4-6` | médio (padrão) | Fontes que exigem síntese: `youtube`, `rss`, `reddit`, `filmes` |
| `claude-opus-4-8` | ~5× mais caro | Qualidade máxima — produção corporativa ou fonte principal do dia |

> As fontes `horoscopo`, `trivia` e `receitas` já têm `model: "claude-haiku-4-5-20251001"` ativo no `config.yaml.example`.

---

## Override por fonte

Qualquer source pode usar um modelo diferente adicionando o campo `model`:

```yaml
- id: horoscopo
  type: horoscopo
  model: "claude-haiku-4-5-20251001"   # só nesta fonte
```

A resolução segue a ordem: **`model` da fonte → `llm.model` global → `claude-sonnet-4-6`**.

---

## Contexto adicional por source (`context`)

Qualquer source aceita um campo `context` para orientar o roteirista — tom, foco temático, público-alvo:

```yaml
sources:
  - id: noticias
    type: rss
    context: "destaque os impactos econômicos para o Brasil"

  - id: tecnologia
    type: rss
    context: "público jovem universitário, linguagem informal"
```

Via CLI ou MCP, use o sufixo `|contexto` para instrução pontual (sobrescreve o `context` do config):

```bash
python main.py "noticias|ignore esportes, foca em política"
python main.py "url:https://exemplo.com|extraia os pontos técnicos"
```

---

## Modelos disponíveis para o agente MCP (`llm.modelos`)

O campo `llm.modelos` define quais modelos o agente MCP pode usar. Serve para **descoberta** (`listar_modelos()`) e **restrição** — se configurado, `gerar_episodios()` rejeita modelos fora da lista.

```yaml
llm:
  model: "claude-sonnet-4-6"
  modelos:
    - id: "claude-haiku-4-5-20251001"
      descricao: "rapido e economico — fontes simples, volume alto"
    - id: "claude-sonnet-4-6"
      descricao: "qualidade padrao — uso geral"
    - id: "claude-opus-4-8"
      descricao: "maxima qualidade — conteudo complexo ou criativo"
    # - id: "gpt-4o-mini"
    #   descricao: "OpenAI — alternativa economica"
```

Se `llm.modelos` for omitido, qualquer modelo é aceito.
