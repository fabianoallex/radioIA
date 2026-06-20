import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import {
  Activity, Headphones, HardDrive, Zap,
  CalendarDays, Clock, CheckCircle2, Play,
  Square, Radio,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

interface Episode {
  pasta: string
  horario: string
  fonte: string
  nome: string
  duracao_seg: number
}

interface ScheduledSlot {
  time: string
  label: string
  sources: string[]
}

interface SystemStatus {
  radio:     { nome: string }
  scheduler: { ativo: boolean; pid: number | null; ultimo_tick_seg: number | null }
  player:    { ativo: boolean }
  hoje:      { data: string; total: number; duracao_total: string; episodios: Episode[] }
  disco:     { output_mb: number; disco_livre_gb: number }
  proximos:  ScheduledSlot[]
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={cn(
      "inline-block size-2 rounded-full shrink-0",
      active ? "bg-emerald-500" : "bg-zinc-600",
    )} />
  )
}

function StatCard({
  icon: Icon, label, value, sub, active,
}: {
  icon: React.ElementType
  label: string
  value: string
  sub?: string
  active?: boolean
}) {
  return (
    <div className="rounded-lg border bg-card p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
        <Icon className="size-4 text-muted-foreground" />
      </div>
      <div>
        <div className="flex items-center gap-2">
          {active !== undefined && <StatusDot active={active} />}
          <span className="text-2xl font-semibold text-foreground leading-none">{value}</span>
        </div>
        {sub && <p className="text-xs text-muted-foreground mt-1.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery<SystemStatus>({
    queryKey: ["system"],
    queryFn: () => api.get<SystemStatus>("/system"),
    refetchInterval: 15_000,
  })

  const schedulerMutation = useMutation({
    mutationFn: (action: "start" | "stop") =>
      api.post("/system/scheduler", { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system"] })
    },
  })

  const schedulerActive = data?.scheduler.ativo ?? false

  const today = new Date().toLocaleDateString("pt-BR", {
    weekday: "long", day: "numeric", month: "long",
  })

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-foreground">
            {isLoading ? "RadioIA" : (data?.radio.nome ?? "RadioIA")}
          </h1>
          <p className="text-sm text-muted-foreground capitalize">{today}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/generator"
            className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Zap className="size-3.5" />
            Gerar episódios
          </Link>
          <button
            onClick={() => schedulerMutation.mutate(schedulerActive ? "stop" : "start")}
            disabled={schedulerMutation.isPending || isLoading}
            className={cn(
              "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50",
              schedulerActive
                ? "border-emerald-600/40 bg-emerald-600/10 text-emerald-400 hover:bg-emerald-600/20"
                : "border-border bg-secondary text-secondary-foreground hover:bg-secondary/70",
            )}
          >
            {schedulerActive
              ? <Square className="size-3.5" />
              : <Play className="size-3.5" />
            }
            {schedulerMutation.isPending
              ? "Aguarde..."
              : schedulerActive ? "Parar scheduler" : "Iniciar scheduler"
            }
          </button>
        </div>
      </div>

      {/* Scroll area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {isError && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            Erro ao conectar com a API. Verifique se o servidor está rodando.
          </div>
        )}

        {isLoading ? (
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="rounded-lg border bg-card p-4 h-24 animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-4 gap-4">
              <StatCard
                icon={Activity}
                label="Scheduler"
                value={schedulerActive ? "Ativo" : "Parado"}
                sub={
                  schedulerActive && data?.scheduler.ultimo_tick_seg != null
                    ? `Último tick há ${data.scheduler.ultimo_tick_seg}s`
                    : undefined
                }
                active={schedulerActive}
              />
              <StatCard
                icon={Radio}
                label="Episódios hoje"
                value={String(data?.hoje.total ?? 0)}
                sub={
                  data?.hoje.total
                    ? `Total: ${data.hoje.duracao_total}`
                    : "Nenhum ainda"
                }
              />
              <StatCard
                icon={Headphones}
                label="Player"
                value={data?.player.ativo ? "Online" : "Offline"}
                active={data?.player.ativo}
                sub={data?.player.ativo ? "localhost:5000" : "python serve.py"}
              />
              <StatCard
                icon={HardDrive}
                label="Output"
                value={`${data?.disco.output_mb ?? 0} MB`}
                sub={`${data?.disco.disco_livre_gb ?? 0} GB livres no disco`}
              />
            </div>

            {/* Episodes + Next scheduled */}
            <div className="grid grid-cols-2 gap-6">
              {/* Today's episodes */}
              <div className="rounded-lg border bg-card flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
                  <span className="text-sm font-medium">Episódios de hoje</span>
                  <span className="text-xs text-muted-foreground">
                    {data?.hoje.total ?? 0} gerado(s)
                  </span>
                </div>
                <div className="divide-y overflow-y-auto">
                  {data?.hoje.episodios?.length ? (
                    data.hoje.episodios.map((ep) => (
                      <div key={ep.pasta} className="flex items-center gap-3 px-4 py-2.5">
                        <span className="text-xs font-mono text-muted-foreground w-10 shrink-0">
                          {ep.horario}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-foreground truncate">
                            {ep.nome || ep.fonte}
                          </p>
                        </div>
                        <span className="text-xs text-muted-foreground shrink-0">
                          {Math.round(ep.duracao_seg / 60)}min
                        </span>
                        <CheckCircle2 className="size-3.5 text-emerald-500 shrink-0" />
                      </div>
                    ))
                  ) : (
                    <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                      Nenhum episódio gerado hoje
                    </div>
                  )}
                </div>
              </div>

              {/* Next scheduled */}
              <div className="rounded-lg border bg-card flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
                  <span className="text-sm font-medium">Próximos agendamentos</span>
                  <CalendarDays className="size-4 text-muted-foreground" />
                </div>
                <div className="divide-y overflow-y-auto">
                  {data?.proximos?.length ? (
                    data.proximos.map((slot, i) => (
                      <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                        <Clock className="size-3.5 text-muted-foreground shrink-0" />
                        <span className="text-xs font-mono text-muted-foreground w-10 shrink-0">
                          {slot.time}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-foreground truncate">
                            {slot.label || slot.sources?.join(", ")}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                      Sem agendamentos pendentes
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
