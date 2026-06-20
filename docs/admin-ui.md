# Admin UI

Interface web para gerenciar a rádio sem editar o `config.yaml` diretamente. Permite configurar fontes, grade, spots, narradores e gerar episódios com acompanhamento em tempo real.

---

## Subir em produção

```bash
# Build da interface (necessário uma vez, ou após mudanças de UI)
cd ui && npm install && npm run build && cd ..

# Subir a API (já serve o ui/dist/ automaticamente)
uvicorn api.main:app --port 5001
```

Acesse: `http://localhost:5001`

---

## Modo desenvolvimento (hot-reload)

```bash
# Terminal 1 — API
uvicorn api.main:app --port 5001

# Terminal 2 — Vite dev server
cd ui && npm run dev
```

Acesse: `http://localhost:5173`

O Vite faz proxy das chamadas `/api` para a API em `:5001`.

---

## Rodando dev e produção no mesmo PC

| Serviço | Dev | Produção |
|---------|-----|----------|
| API / Admin UI | porta 5001 | porta 5002 |
| Player (`serve.py`) | porta 5000 | porta 5000 |
| Vite (dev) | porta 5173 | não usa |

```bash
# Produção (segunda pasta do projeto)
$env:PLAYER_PORT = "5000"; uvicorn api.main:app --port 5002

# Dev (pasta original)
uvicorn api.main:app --port 5001
cd ui && npm run dev
```

`PLAYER_PORT` informa ao Admin UI em qual porta o player web (`serve.py`) está rodando — usado para o link "Abrir player" no menu e o status no Dashboard. Se omitido, assume `5000`.

---

## Funcionalidades

- **Dashboard** — status do scheduler, player e episódios do dia
- **Gerador** — seleciona fontes, preenche contexto e acompanha a geração em tempo real via streaming
- **Fontes** — visualiza e edita as fontes configuradas
- **Grade** — gerencia a programação com timeline visual
- **Episódios** — navega por data, ouve episódios no browser e exporta ZIP
- **Spots** — CRUD de spots e configuração de frequência de injeção
- **Configurações** — narradores, modelo LLM, vinheta, downloads, avisos, intro de boas-vindas

---

## Dependências

**Backend:**
```bash
pip install fastapi uvicorn
```

**Frontend** (Node.js 18+):
```bash
cd ui && npm install
```
