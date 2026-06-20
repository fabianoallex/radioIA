import { useState, useCallback } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Zap, RotateCcw, ChevronDown, ChevronUp } from "lucide-react"
import {
  Rss, Music, Layers, PlayCircle, BarChart2, Newspaper,
  TrendingUp, MessageSquare, Star, Film, HelpCircle,
  BookOpen, Utensils, Book, Mic, Package,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import { LogStream } from "@/components/LogStream"

const ICON_MAP: Record<string, React.ElementType> = {
  youtube:          PlayCircle,
  rss:              Rss,
  music:            Music,
  layers:           Layers,
  "bar-chart-2":    BarChart2,
  "trending-up":    TrendingUp,
  newspaper:        Newspaper,
  "message-square": MessageSquare,
  star:             Star,
  "book-open":      BookOpen,
  utensils:         Utensils,
  film:             Film,
  book:             Book,
  "help-circle":    HelpCircle,
  mic:              Mic,
  package:          Package,
}

function SourceIcon({ icon }: { icon: string }) {
  const Icon = ICON_MAP[icon] ?? Package
  return <Icon className="size-4 shrink-0" />
}

interface Source {
  id: string
  name: string
  type: string
  enabled: boolean
  plugin_info: { icon: string }
}

interface Episode {
  pasta: string
  horario: string
  nome: string
  duracao_seg: number
  fonte: string
}

export default function Generator() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [contexts, setContexts] = useState<Record<string, string>>({})
  const [expandedCtx, setExpandedCtx] = useState<Set<string>>(new Set())
  const [isGenerating, setIsGenerating] = useState(false)
  const [logLines, setLogLines] = useState<string[]>([])
  const [done, setDone] = useState<boolean | null>(null)
  const [newEpisodes, setNewEpisodes] = useState<Episode[]>([])

  const { data: sources = [] } = useQuery<Source[]>({
    queryKey: ["sources"],
    queryFn: () => api.get<Source[]>("/sources"),
    select: (data) => data.filter((s) => s.enabled !== false),
  })

  const toggleSource = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleCtx = (id: string) => {
    setExpandedCtx((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const reset = () => {
    setLogLines([])
    setDone(null)
    setNewEpisodes([])
  }

  const handleGenerate = useCallback(async () => {
    if (!selected.size || isGenerating) return
    reset()
    setIsGenerating(true)

    const sourceArgs = Array.from(selected).map((id) => {
      const ctx = contexts[id]?.trim()
      return ctx ? `${id}|${ctx}` : id
    })

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: sourceArgs }),
      })

      if (!res.body) throw new Error("Sem stream")

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ""

      while (true) {
        const { done: streamDone, value } = await reader.read()
        if (streamDone) break
        buf += decoder.decode(value, { stream: true })

        const parts = buf.split("\n\n")
        buf = parts.pop() ?? ""

        for (const part of parts) {
          const dataLine = part.split("\n").find((l) => l.startsWith("data: "))
          if (!dataLine) continue
          const data = dataLine.slice(6)
          if (data === "[CONCLUIDO]") {
            setDone(true)
            setLogLines((prev) => [...prev, data])
          } else if (data.startsWith("[ERRO")) {
            setDone(false)
            setLogLines((prev) => [...prev, data])
          } else {
            setLogLines((prev) => [...prev, data])
          }
        }
      }
    } catch (e) {
      setLogLines((prev) => [...prev, `[ERRO:${e}]`])
      setDone(false)
    } finally {
      setIsGenerating(false)
      // Refresh episodes + system data
      queryClient.invalidateQueries({ queryKey: ["system"] })
      // Load today's new episodes
      try {
        const eps = await api.get<{ episodios: Episode[] }>("/episodes/today")
        setNewEpisodes(eps.episodios ?? [])
      } catch {
        // endpoint will exist in Phase 4
      }
    }
  }, [selected, contexts, isGenerating, queryClient])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Gerador</h1>
          <p className="text-sm text-muted-foreground">
            {selected.size === 0
              ? "Selecione fontes para gerar"
              : `${selected.size} fonte(s) selecionada(s)`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(logLines.length > 0 || done !== null) && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <RotateCcw className="size-3.5" />
              Limpar
            </button>
          )}
          <button
            onClick={handleGenerate}
            disabled={selected.size === 0 || isGenerating}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Zap className="size-3.5" />
            {isGenerating ? "Gerando..." : "Gerar"}
          </button>
        </div>
      </div>

      {/* Body: two columns */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left — source selection */}
        <div className="w-72 shrink-0 border-r flex flex-col overflow-hidden">
          <p className="px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide border-b">
            Fontes ativas
          </p>
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {sources.map((src) => {
              const isSelected = selected.has(src.id)
              const ctxOpen = expandedCtx.has(src.id)

              return (
                <div key={src.id}>
                  <div
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-3 py-2 cursor-pointer transition-colors group",
                      isSelected
                        ? "bg-primary/10 border border-primary/30"
                        : "hover:bg-muted/50 border border-transparent",
                    )}
                    onClick={() => toggleSource(src.id)}
                  >
                    {/* Checkbox */}
                    <div className={cn(
                      "size-4 rounded border-2 shrink-0 flex items-center justify-center transition-colors",
                      isSelected
                        ? "border-primary bg-primary"
                        : "border-muted-foreground/40 group-hover:border-muted-foreground",
                    )}>
                      {isSelected && (
                        <svg className="size-2.5 text-white" fill="none" viewBox="0 0 10 8">
                          <path d="M1 4l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </div>

                    <SourceIcon icon={src.plugin_info.icon} />

                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground truncate">{src.name}</p>
                      <p className="text-xs text-muted-foreground">{src.type}</p>
                    </div>

                    {isSelected && (
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleCtx(src.id) }}
                        className="p-0.5 text-muted-foreground hover:text-foreground"
                        title="Adicionar contexto"
                      >
                        {ctxOpen
                          ? <ChevronUp className="size-3.5" />
                          : <ChevronDown className="size-3.5" />}
                      </button>
                    )}
                  </div>

                  {/* Context input */}
                  {isSelected && ctxOpen && (
                    <div className="px-3 pb-2 pt-1">
                      <input
                        type="text"
                        placeholder="Contexto/tom opcional..."
                        value={contexts[src.id] ?? ""}
                        onChange={(e) =>
                          setContexts((prev) => ({ ...prev, [src.id]: e.target.value }))
                        }
                        className="w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Select all / none */}
          <div className="border-t p-3 flex gap-2">
            <button
              onClick={() => setSelected(new Set(sources.map((s) => s.id)))}
              className="flex-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Selecionar todas
            </button>
            <span className="text-muted-foreground/30">|</span>
            <button
              onClick={() => setSelected(new Set())}
              className="flex-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Limpar
            </button>
          </div>
        </div>

        {/* Right — log + result */}
        <div className="flex-1 flex flex-col overflow-hidden p-6 gap-4">
          {/* Log */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Log de geração
              </span>
              {isGenerating && (
                <span className="flex items-center gap-1.5 text-xs text-primary">
                  <span className="inline-block size-1.5 rounded-full bg-primary animate-pulse" />
                  Gerando...
                </span>
              )}
              {done === true && (
                <span className="text-xs text-emerald-400">✓ Concluído</span>
              )}
              {done === false && (
                <span className="text-xs text-red-400">✗ Erro</span>
              )}
            </div>
            <LogStream lines={logLines} className="flex-1" />
          </div>

          {/* Generated episodes (after completion) */}
          {newEpisodes.length > 0 && (
            <div className="shrink-0">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Episódios gerados
              </p>
              <div className="space-y-2">
                {newEpisodes.map((ep) => (
                  <div
                    key={ep.pasta}
                    className="flex items-center gap-3 rounded-lg border bg-card px-4 py-2.5"
                  >
                    <span className="text-xs font-mono text-muted-foreground w-10">{ep.horario}</span>
                    <span className="flex-1 text-sm text-foreground">{ep.nome || ep.fonte}</span>
                    <span className="text-xs text-muted-foreground">{Math.round(ep.duracao_seg / 60)}min</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
