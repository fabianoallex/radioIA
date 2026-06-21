import { useState, useMemo } from "react"
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query"
import {
  ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  Download, Archive, Repeat,
  Rss, Music, PlayCircle, BarChart2, TrendingUp,
  MessageSquare, Star, Film, BookOpen, Utensils,
  Book, HelpCircle, Mic, Package, Radio,
  Eye, EyeOff, Trash2, ExternalLink, Cpu, Clock,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

// ─── icon map ────────────────────────────────────────────────────
const ICON_MAP: Record<string, React.ElementType> = {
  youtube:       PlayCircle,
  rss:           Rss,
  music:         Music,
  utility:       BarChart2,
  clipping:      TrendingUp,
  clipping_auto: TrendingUp,
  reddit:        MessageSquare,
  horoscopo:     Star,
  filmes:        Film,
  efemerides:    BookOpen,
  receitas:      Utensils,
  biblia:        Book,
  trivia:        HelpCircle,
  podcast:       Mic,
  combined:      Radio,
}

function EpIcon({ sourceId }: { sourceId: string }) {
  const key = Object.keys(ICON_MAP).find((k) => sourceId.includes(k))
  const Icon = (key ? ICON_MAP[key] : null) ?? Package
  return <Icon className="size-4 shrink-0" />
}

// ─── helpers ────────────────────────────────────────────────────
function fmtDuration(secs: number): string {
  if (!secs) return "—"
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  if (h > 0) return `${h}h ${m}min`
  if (m > 0) return `${m}min ${s}s`
  return `${s}s`
}

function fmtBytes(b: number): string {
  if (!b) return ""
  const mb = b / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`
}

function isoToDisplay(dt: string): string {
  const [y, m, d] = dt.split("-")
  const months = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
  return `${Number(d)} de ${months[Number(m) - 1]} de ${y}`
}

function todayIso(): string {
  const d = new Date()
  return d.getFullYear() + "-" +
    String(d.getMonth() + 1).padStart(2, "0") + "-" +
    String(d.getDate()).padStart(2, "0")
}

// ─── types ──────────────────────────────────────────────────────
interface EpLink {
  title: string
  channel: string
  url: string
  views: number
  published_at: string
  start_time_seconds?: number
}

interface Generation {
  model?: string
  started_at?: string
  finished_at?: string
  total_seconds?: number
  llm_seconds?: number
  tts_seconds?: number
  mix_seconds?: number
  script_words?: number
  items_count?: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
}

interface Episode {
  pasta: string
  horario: string
  source_id: string
  nome: string
  duracao_seg: number
  tamanho_bytes: number
  date: string
  status: "published" | "draft"
  links?: EpLink[]
  generation?: Generation
  replay_of?: string
}

// ─── helpers (detalhe) ──────────────────────────────────────────
function fmtReplayOf(replayOf: string, epDate: string): string {
  const parts    = replayOf.split("/")
  const origDate = parts.length >= 2 ? parts[0] : epDate
  const origFld  = parts.length >= 2 ? parts[1] : parts[0]
  const origTime = (origFld.split("_")[0] ?? "").replace("-", "h")
  const dateLabel = origDate !== epDate
    ? `${origDate.slice(8)}/${origDate.slice(5, 7)} às ${origTime}`
    : origTime
  return dateLabel
}

function fmtSecs(s: number | undefined): string {
  if (!s) return "—"
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function fmtNum(n: number | undefined): string {
  if (n === undefined || n === null) return "—"
  return n.toLocaleString("pt-BR")
}

// ─── TextSection (lazy) ─────────────────────────────────────────
function TextSection({ label, url }: { label: string; url: string }) {
  const [open, setOpen] = useState(false)
  const { data, isFetching, isError } = useQuery<string>({
    queryKey: ["ep-text", url],
    queryFn:  () => api.getText(url),
    enabled:  open,
    staleTime: Infinity,
  })
  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
        {label}
      </button>
      {open && (
        <div className="mt-2">
          {isFetching && <p className="text-xs text-muted-foreground">Carregando...</p>}
          {isError   && <p className="text-xs text-destructive">Erro ao carregar.</p>}
          {data && (
            <pre className="text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap break-words bg-muted/40 rounded p-3 max-h-72 overflow-y-auto font-mono">
              {data}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

// ─── EpisodeCard ────────────────────────────────────────────────
function EpisodeCard({ ep, onMutated }: { ep: Episode; onMutated: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const streamUrl  = `/api/episodes/${ep.date}/${ep.pasta}/stream`
  const dlUrl      = `/api/episodes/${ep.date}/${ep.pasta}/download`
  const promptUrl  = `/episodes/${ep.date}/${ep.pasta}/prompt`
  const scriptUrl  = `/episodes/${ep.date}/${ep.pasta}/script`
  const epPath     = `${ep.date}/${ep.pasta}`
  const isDraft    = ep.status === "draft"
  const hasDetails = (ep.links && ep.links.length > 0) || ep.generation

  const toggleStatus = useMutation({
    mutationFn: () => api.patch(`/episodes/${epPath}/status`, {
      status: isDraft ? "published" : "draft",
    }),
    onSuccess: onMutated,
  })

  const replay = useMutation({
    mutationFn: () => api.post(`/episodes/${epPath}/replay`),
    onSuccess: onMutated,
  })

  const remove = useMutation({
    mutationFn: () => api.delete(`/episodes/${epPath}`),
    onSuccess: onMutated,
  })

  const handleDelete = () => {
    if (confirm(`Remover episódio "${ep.nome}" (${ep.horario})?\nOs itens usados voltarão ao histórico.`)) {
      remove.mutate()
    }
  }

  const gen = ep.generation

  return (
    <div className={cn("rounded-lg border bg-card overflow-hidden", isDraft && "border-amber-500/40 opacity-80")}>
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="rounded-md bg-primary/10 p-1.5 shrink-0">
          <EpIcon sourceId={ep.source_id} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-foreground truncate">{ep.nome}</p>
            {isDraft && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 shrink-0">
                rascunho
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">{ep.source_id}</p>
          {ep.replay_of && (
            <p className="text-xs mt-0.5">
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium">
                <Repeat className="size-2.5" />
                replay · original: {fmtReplayOf(ep.replay_of, ep.date)}
              </span>
            </p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs font-mono text-muted-foreground">{ep.horario}</p>
          <p className="text-xs text-muted-foreground">{fmtDuration(ep.duracao_seg)}</p>
        </div>
        <div className="flex items-center gap-1 ml-2">
          {hasDetails && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              title={expanded ? "Ocultar detalhes" : "Ver detalhes"}
            >
              {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>
          )}
          <button
            onClick={() => replay.mutate()}
            disabled={replay.isPending}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            title="Replay — republicar no horário atual"
          >
            <Repeat className={cn("size-3.5", replay.isPending && "animate-spin")} />
          </button>
          <button
            onClick={() => toggleStatus.mutate()}
            disabled={toggleStatus.isPending}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            title={isDraft ? "Publicar" : "Mover para rascunho"}
          >
            {isDraft ? <Eye className="size-3.5" /> : <EyeOff className="size-3.5" />}
          </button>
          <a
            href={dlUrl}
            download
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Download"
          >
            <Download className="size-3.5" />
          </a>
          <button
            onClick={handleDelete}
            disabled={remove.isPending}
            className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-muted transition-colors disabled:opacity-40"
            title="Remover episódio"
          >
            <Trash2 className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Player */}
      <div className="px-4 pb-3">
        <audio controls preload="none" className="w-full h-8" style={{ colorScheme: "dark" }}>
          <source src={streamUrl} type="audio/mpeg" />
        </audio>
        {ep.tamanho_bytes > 0 && (
          <p className="text-right text-xs text-zinc-600 mt-1">{fmtBytes(ep.tamanho_bytes)}</p>
        )}
      </div>

      {/* Details panel */}
      {expanded && (
        <div className="border-t px-4 py-3 space-y-4 text-xs">

          {/* Links / itens */}
          {ep.links && ep.links.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                Itens ({ep.links.length})
              </p>
              <ol className="space-y-1.5">
                {ep.links.map((lnk, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-muted-foreground shrink-0 font-mono">{i + 1}.</span>
                    <div className="min-w-0">
                      <div className="flex items-start gap-1.5">
                        <span className="text-foreground leading-snug">{lnk.title}</span>
                        {lnk.url && (
                          <a
                            href={lnk.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 mt-0.5 text-muted-foreground hover:text-foreground"
                          >
                            <ExternalLink className="size-3" />
                          </a>
                        )}
                      </div>
                      <div className="flex gap-2 text-muted-foreground mt-0.5">
                        {lnk.channel && <span>{lnk.channel}</span>}
                        {lnk.published_at && <span>· {lnk.published_at}</span>}
                        {lnk.views > 0 && <span>· {fmtNum(lnk.views)} views</span>}
                        {lnk.start_time_seconds !== undefined && (
                          <span>· ⏱ {fmtSecs(lnk.start_time_seconds)}</span>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Generation metadata */}
          {gen && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                Geração
              </p>
              <div className="space-y-2">
                {/* Model + timing */}
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {gen.model && (
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Cpu className="size-3" />
                      <span className="font-mono">{gen.model}</span>
                    </span>
                  )}
                  {gen.started_at && (
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Clock className="size-3" />
                      {gen.started_at.slice(11, 16).replace(":", "h")}
                      {gen.finished_at && <> → {gen.finished_at.slice(11, 16).replace(":", "h")}</>}
                    </span>
                  )}
                </div>

                {/* Timing breakdown */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                  {gen.total_seconds !== undefined && (
                    <span>Total: <strong className="text-foreground">{fmtSecs(gen.total_seconds)}</strong></span>
                  )}
                  {gen.llm_seconds !== undefined && (
                    <span>LLM: <strong className="text-foreground">{fmtSecs(gen.llm_seconds)}</strong></span>
                  )}
                  {gen.tts_seconds !== undefined && (
                    <span>TTS: <strong className="text-foreground">{fmtSecs(gen.tts_seconds)}</strong></span>
                  )}
                  {gen.mix_seconds !== undefined && (
                    <span>Mix: <strong className="text-foreground">{fmtSecs(gen.mix_seconds)}</strong></span>
                  )}
                </div>

                {/* Tokens */}
                {gen.total_tokens !== undefined && (
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                    <span>
                      Tokens:{" "}
                      <strong className="text-foreground">{fmtNum(gen.prompt_tokens)}</strong>
                      {" prompt + "}
                      <strong className="text-foreground">{fmtNum(gen.completion_tokens)}</strong>
                      {" completion = "}
                      <strong className="text-foreground">{fmtNum(gen.total_tokens)}</strong>
                    </span>
                  </div>
                )}

                {/* Words / items */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                  {gen.script_words !== undefined && (
                    <span>Roteiro: <strong className="text-foreground">{fmtNum(gen.script_words)}</strong> palavras</span>
                  )}
                  {gen.items_count !== undefined && (
                    <span>Itens: <strong className="text-foreground">{gen.items_count}</strong></span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Prompt e Roteiro */}
          <TextSection label="Prompt" url={promptUrl} />
          <TextSection label="Roteiro" url={scriptUrl} />
        </div>
      )}
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────
export default function Episodes() {
  const [date, setDate] = useState(todayIso())
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["episodes", date] })

  const { data: datesData } = useQuery<{ dates: string[] }>({
    queryKey: ["episode-dates"],
    queryFn:  () => api.get<{ dates: string[] }>("/episodes/dates"),
    staleTime: 60_000,
  })

  const { data, isLoading } = useQuery<{ date: string; episodios: Episode[] }>({
    queryKey: ["episodes", date],
    queryFn:  () => api.get(`/episodes?date=${date}`),
    staleTime: 30_000,
  })

  const episodes = data?.episodios ?? []
  const dates    = datesData?.dates ?? []

  // dates are sorted desc, so prev (earlier) = higher index, next (later) = lower index
  const hasPrev = useMemo(() => dates.indexOf(date) < dates.length - 1, [dates, date])
  const hasNext = useMemo(() => dates.indexOf(date) > 0, [dates, date])
  const goPrev  = () => { const i = dates.indexOf(date); if (i < dates.length - 1) setDate(dates[i + 1]) }
  const goNext  = () => { const i = dates.indexOf(date); if (i > 0) setDate(dates[i - 1]) }

  const totalSecs  = episodes.reduce((s, e) => s + e.duracao_seg, 0)
  const totalBytes = episodes.reduce((s, e) => s + e.tamanho_bytes, 0)
  const zipUrl     = `/api/episodes/${date}/export/zip`

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0 gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <button
            onClick={goPrev}
            disabled={!hasPrev}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30"
          >
            <ChevronLeft className="size-4" />
          </button>

          <input
            type="date"
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
            className="text-sm bg-transparent border border-border rounded-md px-2 py-1 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />

          <button
            onClick={goNext}
            disabled={!hasNext}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30"
          >
            <ChevronRight className="size-4" />
          </button>

          <button
            onClick={() => setDate(todayIso())}
            className={cn(
              "text-xs px-2.5 py-1 rounded-md border transition-colors",
              date === todayIso()
                ? "border-primary text-primary"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            Hoje
          </button>
        </div>

        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-medium text-foreground">{isoToDisplay(date)}</h1>
          {episodes.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {episodes.length} episódio(s) · {fmtDuration(totalSecs)} · {fmtBytes(totalBytes)}
            </p>
          )}
        </div>

        {episodes.length > 0 && (
          <a
            href={zipUrl}
            download
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <Archive className="size-3.5" />
            Exportar ZIP
          </a>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="space-y-3 max-w-3xl">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 rounded-lg border bg-card animate-pulse" />
            ))}
          </div>
        ) : episodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3">
            <Archive className="size-10 text-muted-foreground/30" />
            <p className="text-muted-foreground">Nenhum episódio para {isoToDisplay(date)}</p>
            {dates.length > 0 && date !== dates[0] && (
              <button
                onClick={() => setDate(dates[0])}
                className="text-xs text-primary hover:underline"
              >
                Ver {dates[0]} (mais recente com conteúdo)
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3 max-w-3xl">
            {episodes.map((ep) => (
              <EpisodeCard key={ep.pasta} ep={ep} onMutated={invalidate} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
