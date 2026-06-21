import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  ChevronLeft, ChevronRight, Download, Archive,
  Rss, Music, PlayCircle, BarChart2, TrendingUp,
  MessageSquare, Star, Film, BookOpen, Utensils,
  Book, HelpCircle, Mic, Package, Radio,
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
interface Episode {
  pasta: string
  horario: string
  source_id: string
  nome: string
  duracao_seg: number
  tamanho_bytes: number
  date: string
}

// ─── EpisodeCard ────────────────────────────────────────────────
function EpisodeCard({ ep }: { ep: Episode }) {
  const streamUrl = `/api/episodes/${ep.date}/${ep.pasta}/stream`
  const dlUrl     = `/api/episodes/${ep.date}/${ep.pasta}/download`

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="rounded-md bg-primary/10 p-1.5 shrink-0">
          <EpIcon sourceId={ep.source_id} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{ep.nome}</p>
          <p className="text-xs text-muted-foreground">{ep.source_id}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs font-mono text-muted-foreground">{ep.horario}</p>
          <p className="text-xs text-muted-foreground">{fmtDuration(ep.duracao_seg)}</p>
        </div>
        <a
          href={dlUrl}
          download
          className="ml-2 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Download"
        >
          <Download className="size-3.5" />
        </a>
      </div>

      <div className="px-4 pb-3">
        <audio
          controls
          preload="none"
          className="w-full h-8"
          style={{ colorScheme: "dark" }}
        >
          <source src={streamUrl} type="audio/mpeg" />
        </audio>
        {ep.tamanho_bytes > 0 && (
          <p className="text-right text-xs text-zinc-600 mt-1">{fmtBytes(ep.tamanho_bytes)}</p>
        )}
      </div>
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────
export default function Episodes() {
  const [date, setDate] = useState(todayIso())

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
              <EpisodeCard key={ep.pasta} ep={ep} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
