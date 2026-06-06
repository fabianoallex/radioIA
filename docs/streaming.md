# RadioIA em modo streamer

Este guia mostra como transmitir o RadioIA como uma rádio ao vivo usando **Icecast2** e **Liquidsoap** — sem alterar nada no código existente.

O RadioIA continua gerando episódios normalmente. O Liquidsoap lê a pasta `output/` e os transmite em sequência; quando não há episódios novos, toca as músicas de `music/` como fallback. Quando um novo episódio é gerado pelo scheduler, o Liquidsoap o detecta automaticamente e o insere na transmissão.

```
scheduler.py  →  output/hoje/  ←  liquidsoap  →  icecast2  →  ouvintes
```

---

## Pré-requisitos

```bash
# Ubuntu / Debian
sudo apt install icecast2 liquidsoap

# macOS (Homebrew)
brew install icecast liquidsoap
```

Versões testadas: Icecast2 2.4+, Liquidsoap 2.x.

---

## 1. Configurar o Icecast2

Edite `/etc/icecast2/icecast.xml` e ajuste as senhas:

```xml
<icecast>
  <location>Brasil</location>
  <admin>admin@seudominio.com</admin>

  <limits>
    <clients>100</clients>
    <sources>2</sources>
  </limits>

  <authentication>
    <source-password>SOURCE_PASSWORD</source-password>
    <relay-password>RELAY_PASSWORD</relay-password>
    <admin-user>admin</admin-user>
    <admin-password>ADMIN_PASSWORD</admin-password>
  </authentication>

  <hostname>localhost</hostname>

  <listen-socket>
    <port>8000</port>
  </listen-socket>

  <mount>
    <mount-name>/radio</mount-name>
    <stream-name>RadioIA</stream-name>
    <stream-description>Rádio personalizada com IA</stream-description>
  </mount>

  <paths>
    <logdir>/var/log/icecast2</logdir>
    <webroot>/usr/share/icecast2/web</webroot>
    <adminroot>/usr/share/icecast2/admin</adminroot>
  </paths>
</icecast>
```

Inicie o Icecast2:

```bash
sudo systemctl start icecast2
sudo systemctl enable icecast2   # inicia automaticamente no boot
```

---

## 2. Script do Liquidsoap

Crie o arquivo `liquidsoap/radio.liq` dentro do diretório do RadioIA:

```liquidsoap
#!/usr/bin/env liquidsoap

# ── Configuração ──────────────────────────────────────────────────────────────
let radioia_dir = "/caminho/para/radioIA"
let icecast_host = "localhost"
let icecast_port = 8000
let icecast_pass = "SOURCE_PASSWORD"   # mesma senha do icecast.xml
let icecast_mount = "/radio"

# ── Data de hoje (atualiza à meia-noite) ─────────────────────────────────────
def today_dir() =
  date = list.hd(get_process_lines("date +%Y-%m-%d"), default="")
  "#{radioia_dir}/output/#{date}"
end

# ── Episódios do dia ──────────────────────────────────────────────────────────
# Verifica novos arquivos a cada 30 segundos
episodes = playlist(
  reload = 30,
  mode = "normal",
  today_dir()
)

# ── Músicas locais (fallback) ─────────────────────────────────────────────────
music = playlist(
  reload = false,
  mode = "randomize",
  loop = true,
  "#{radioia_dir}/music"
)

# ── Lógica de fallback ────────────────────────────────────────────────────────
# Toca episódios quando disponíveis, cai para músicas quando não há nada
radio = fallback(track_sensitive = true, [episodes, music])

# ── Saída para Icecast ────────────────────────────────────────────────────────
output.icecast(
  %mp3(bitrate = 128, samplerate = 44100),
  host = icecast_host,
  port = icecast_port,
  password = icecast_pass,
  mount = icecast_mount,
  name = "RadioIA",
  description = "Rádio personalizada com IA",
  radio
)
```

Teste o script antes de rodar como serviço:

```bash
liquidsoap liquidsoap/radio.liq
```

---

## 3. Rodar como serviço (Linux)

Crie `/etc/systemd/system/radioia-stream.service`:

```ini
[Unit]
Description=RadioIA Liquidsoap Stream
After=network.target icecast2.service
Requires=icecast2.service

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/caminho/para/radioIA
ExecStart=/usr/bin/liquidsoap liquidsoap/radio.liq
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Ative o serviço:

```bash
sudo systemctl daemon-reload
sudo systemctl start radioia-stream
sudo systemctl enable radioia-stream
```

O scheduler também deve rodar como serviço. Crie `/etc/systemd/system/radioia-scheduler.service`:

```ini
[Unit]
Description=RadioIA Scheduler
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/caminho/para/radioIA
ExecStart=/usr/bin/python3 scheduler.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start radioia-scheduler
sudo systemctl enable radioia-scheduler
```

---

## 4. Rodar como serviço (Windows)

No Windows, use o **NSSM** (Non-Sucking Service Manager) para transformar qualquer processo em serviço:

```powershell
# Instale o NSSM: https://nssm.cc
nssm install RadioIA-Stream liquidsoap "C:\radioIA\liquidsoap\radio.liq"
nssm install RadioIA-Scheduler python "C:\radioIA\scheduler.py"
nssm start RadioIA-Stream
nssm start RadioIA-Scheduler
```

---

## 5. Acessar o stream

| Acesso | URL |
|--------|-----|
| Rede local | `http://IP-DO-SERVIDOR:8000/radio` |
| Admin Icecast | `http://IP-DO-SERVIDOR:8000/admin` |
| Painel de status | `http://IP-DO-SERVIDOR:8000` |

O stream é compatível com qualquer player que suporte MP3 over HTTP: VLC, navegadores, apps de rádio, Chromecast, etc.

Para expor externamente, aponte seu domínio para o servidor e configure um proxy reverso (nginx ou Caddy) na porta 80/443.

---

## Comportamento ao longo do dia

```
07:00  Scheduler gera episódio  →  Liquidsoap detecta em até 30s  →  entra na transmissão
07:08  Episódio termina         →  sem novos arquivos              →  cai para músicas
07:30  Novo episódio gerado     →  Liquidsoap detecta              →  interrompe música  →  toca episódio
...
```

Todos os ouvintes conectados fazem a transição ao mesmo tempo, como numa rádio convencional.

---

## Diferenças em relação ao player web

| | Player web (`serve.py`) | Modo streamer |
|--|------------------------|---------------|
| Cada ouvinte | Escolhe o episódio | Ouve o mesmo que todos |
| Entrada no meio | Começa do início | Entra no ponto atual |
| Pausa / volta | Sim | Não |
| Infraestrutura | Só Python | Icecast2 + Liquidsoap |
| Escala | Poucos ouvintes | Centenas simultâneos |
| Listagem em apps de rádio | Não | Sim (TuneIn, etc.) |

Os dois modos podem coexistir no mesmo servidor — `serve.py` na porta 5000 para uso pessoal/interno, Icecast na porta 8000 para transmissão pública.
