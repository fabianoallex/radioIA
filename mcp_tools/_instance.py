from mcp.server.fastmcp import FastMCP

_INSTRUCTIONS = """\
RadioIA — gerador de rádio por IA. Gerencie episódios, grade e configuração por conversa.

RECURSOS (resources): além das ferramentas de ação, este servidor expõe dados via resources
com URIs radioia://. Resources não aparecem na lista de ferramentas — use list_resources
para descobri-los e read_resource para lê-los. Sempre prefira resources para consultas.

Comece cada sessão lendo radioia://briefing: ele traz um snapshot completo do estado atual
(scheduler, episódios de hoje, próximos agendamentos, notas operacionais).

Resources disponíveis:
  radioia://briefing          snapshot operacional completo — leia sempre ao iniciar
  radioia://grade             grade de programação com status de execução
  radioia://episodios         episódios gerados hoje
  radioia://episodios/{data}  episódios de uma data específica (YYYY-MM-DD)
  radioia://episodio/{data}/{pasta}  roteiro e metadados de um episódio
  radioia://fontes            fontes configuradas com tipo e status
  radioia://config            configuração completa do config.yaml
  radioia://config/{secao}    seção específica (sources, llm, radio, tts…)
  radioia://sistema           status do scheduler, player, API keys e disco
  radioia://log               últimas 50 linhas do scheduler.log
  radioia://log/{linhas}      últimas N linhas do scheduler.log
  radioia://modelos           modelos LLM disponíveis para geração
  radioia://historico         histórico de conteúdos já veiculados
  radioia://geracao           estado da geração em andamento
  radioia://player            estado do player web e próximo episódio agendado
  radioia://spots             spots configurados com tipo e cache de áudio
  radioia://jamendo           cache local do Jamendo (faixas e tamanho)
  radioia://intro             configuração e status da intro de boas-vindas
  radioia://zips-wp           ZIPs de exportação do WhatsApp por fonte
"""

mcp = FastMCP("RadioIA", instructions=_INSTRUCTIONS)
