# Motor de voz (TTS)

O RadioIA suporta múltiplos provedores de síntese de voz. O padrão é **Edge TTS** (gratuito, sem chave de API). Para trocar, adicione a seção `tts:` ao `config.yaml`.

---

## Provedores disponíveis

| Provider | Qualidade | Custo | Pacote extra |
|----------|-----------|-------|--------------|
| `edge_tts` (padrão) | Boa | Gratuito | — |
| `openai` | Muito boa | Pago por caractere | `pip install openai` |
| `elevenlabs` | Excelente | Pago (tier gratuito limitado) | `pip install elevenlabs` |
| `google` | Muito boa | Pago (tier gratuito generoso) | `pip install google-cloud-texttospeech` |

---

## Configuração básica

```yaml
tts:
  provider: openai          # edge_tts | openai | elevenlabs | google
  openai:
    api_key_env: OPENAI_API_KEY
    model: tts-1-hd         # tts-1 (rápido) | tts-1-hd (maior qualidade)
```

---

## voice_map — troca de provider sem alterar narradores

Cada provider usa nomes de voz diferentes. O `voice_map` converte automaticamente os nomes configurados nos narradores para o equivalente no provider escolhido:

```yaml
tts:
  provider: openai
  openai:
    api_key_env: OPENAI_API_KEY
    model: tts-1-hd
    voice_map:
      pt-BR-ThalitaMultilingualNeural: nova    # feminino, natural
      pt-BR-AntonioNeural: onyx                # masculino, profundo
      pt-BR-FranciscaNeural: shimmer           # feminino, expressivo
```

Sem `voice_map`, o valor do campo `voice` de cada narrador é enviado diretamente ao provider.

> A vinheta (ID da rádio) usa o mesmo provider e também respeita o `voice_map`.

---

## Narradores

Configure de 1 a 3 narradores. O Claude distribui as falas de acordo com as personalidades.

```yaml
narrators:
  - name: "Ana"
    voice: "pt-BR-ThalitaMultilingualNeural"
    personality: "descontraida, curiosa e bem-humorada"

  - name: "Carlos"
    voice: "pt-BR-AntonioNeural"
    personality: "analitico e direto"

  - name: "Julia"           # terceiro narrador (opcional)
    voice: "pt-BR-FranciscaNeural"
    personality: "irreverente e critica"
```

---

## Vinheta

```yaml
vinheta:
  voice: "pt-BR-FranciscaNeural"
  rate: "+20%"    # velocidade da fala

  # Os textos são gerados automaticamente a partir de radio.name.
  # Descomente apenas se quiser um texto personalizado:
  # abertura: "Rádio Empresa XYZ — sua rádio personalizada!"
  # id: "Rádio Empresa XYZ!"
  # encerramento: "Rádio Empresa XYZ — até o próximo episódio!"
```

---

## Referência de vozes por provider

### Edge TTS (padrão) — vozes pt-BR

| Voz | Gênero |
|-----|--------|
| `pt-BR-ThalitaMultilingualNeural` | Feminino |
| `pt-BR-AntonioNeural` | Masculino |
| `pt-BR-FranciscaNeural` | Feminino |

### OpenAI — vozes únicas (multilíngues)

`alloy`, `ash`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`

### ElevenLabs

Use o `voice_id` da Voice Library. Modelos: `eleven_multilingual_v2` (padrão), `eleven_turbo_v2_5`

### Google Cloud TTS — vozes pt-BR recomendadas

| Voz | Gênero | Qualidade |
|-----|--------|-----------|
| `pt-BR-Studio-B` | Masculino | Studio (melhor) |
| `pt-BR-Studio-C` | Feminino | Studio (melhor) |
| `pt-BR-Neural2-A` | Feminino | Neural2 |
| `pt-BR-Neural2-B` | Masculino | Neural2 |
| `pt-BR-Wavenet-A` | Feminino | WaveNet |

Exemplo completo para Google:

```yaml
tts:
  provider: google
  google:
    credentials_env: GOOGLE_APPLICATION_CREDENTIALS   # path do service account JSON
    language_code: pt-BR
    voice_map:
      pt-BR-ThalitaMultilingualNeural: pt-BR-Studio-C
      pt-BR-AntonioNeural: pt-BR-Studio-B
      pt-BR-FranciscaNeural: pt-BR-Neural2-A
```

---

## Clips de hora (speaking clock)

Os avisos de hora no player usam clips de áudio pré-gravados para evitar latência. O sistema mantém **83 clips atômicos** (24 horas + 59 minutos) combinados em tempo de execução para cada HH:MM.

Os clips são gerados automaticamente em background quando o `serve.py` inicia. Para gerar manualmente:

```bash
python main.py --gen-time-clips           # gera os que faltam (~1 min)
python main.py --gen-time-clips --force   # regenera todos (ex: mudou a voz)
```

---

## Testar TTS sem gerar episódio

Via MCP: `testar_tts("Bem-vindos à nossa rádio!")`

Gera `output/tts_test.mp3` para validar a configuração.
