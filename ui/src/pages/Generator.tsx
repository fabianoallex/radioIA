import { useState, useCallback } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Zap, RotateCcw, ChevronDown, ChevronUp, Link, List } from "lucide-react"
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

type Mode = "fontes" | "url"

export default function Generator() {
  const queryClient = useQueryClient()

  const [mode, setMode] = useState<Mode>("fontes")

  // modo fontes
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [contexts, setContexts] = useState<Record<string, string>>({})
  const [expandedCtx, setExpandedCtx] = useState<Set<string>>(new Set())

  // modo url
  const [urlText, setUrlText] = useState("")
  const [urlContext, setUrlContext] = useState("")

  // compartilhado
  const [publish, setPublish] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [logLines, setLogLines] = useState<string[]>([])
  const [done, setDone] = useState<boolean | null>(null)

  const { data: sources = [] } = useQuery<Source[]>({
    queryKey: ["sources"],
    queryFn: () => api.get<Source[]>("/sources"),
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
  }

  const canGenerate = mode === "fontes"
    ? selected.size > 0
    : urlText.trim().split("\n").some((l) => l.trim().startsWith("http"))

  const buildSourceArgs = (): string[] => {
    if (mode === "fontes") {
      return Array.from(selected).map((id) => {
        const ctx = contexts[id]?.trim()
        return ctx ? `${id}|${ctx}` : id
      })
    }
    // modo url: junta todas as URLs válidas em um único arg
    const urls = urlText
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.startsWith("http"))
      .join(",")
    const ctx = urlContext.trim()
    return [ctx ? `url:${urls}|${ctx}` : `url:${urls}`]
  }

  const handleGenerate = useCallback(async () => {
    if (!canGenerate || isGenerating) return
    reset()
    setIsGenerating(true)

    let success = false

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: buildSourceArgs(), publicar: publish }),
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
            success = true
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
      queryClient.invalidateQueries({ queryKey: ["system"] })
      if (success) {
        setSelected(new Set())
        setContexts({})
        setExpandedCtx(new Set())
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, selected, contexts, urlText, urlContext, isGenerating, queryClient])

  const subtitle = mode === "fontes"
    ? (selected.size === 0 ? "Selecione fontes para gerar" : `${selected.size} fonte(s) selecionada(s)`)
    : "Cole URLs para gerar um episódio"

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Gerador</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
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
            disabled={!canGenerate || isGenerating}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Zap className="size-3.5" />
            {isGenerating ? "Gerando..." : "Gerar"}
          </button>
        </div>
      </div>

      {/* Body: two columns */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-72 shrink-0 border-r flex flex-col overflow-hidden">

          {/* Tab switcher */}
          <div className="flex border-b shrink-0">
            <button
              onClick={() => setMode("fontes")}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors",
                mode === "fontes"
                  ? "text-foreground border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <List className="size-3.5" />
              Fontes
            </button>
            <button
              onClick={() => setMode("url")}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors",
                mode === "url"
                  ? "text-foreground border-b-2 border-primary -mb-px"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Link className="size-3.5" />
              URL
            </button>
          </div>

          {/* Fontes mode */}
          {mode === "fontes" && (
            <>
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

                        {src.enabled === false && (
                          <span className="text-xs text-muted-foreground/50 shrink-0">off</span>
                        )}

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
            </>
          )}

          {/* URL mode */}
          {mode === "url" && (
            <div className="flex-1 flex flex-col p-3 gap-3 overflow-hidden">
              <div className="flex-1 flex flex-col gap-1 min-h-0">
                <label className="text-xs text-muted-foreground">
                  URLs <span className="text-muted-foreground/50">(uma por linha)</span>
                </label>
                <textarea
                  value={urlText}
                  onChange={(e) => setUrlText(e.target.value)}
                  placeholder={"https://exemplo.com/artigo\nhttps://youtube.com/watch?v=..."}
                  className="flex-1 resize-none text-xs rounded border bg-input px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring font-mono min-h-0"
                />
              </div>
              <div className="flex flex-col gap-1 shrink-0">
                <label className="text-xs text-muted-foreground">
                  Contexto <span className="text-muted-foreground/50">(opcional)</span>
                </label>
                <input
                  type="text"
                  value={urlContext}
                  onChange={(e) => setUrlContext(e.target.value)}
                  placeholder="Ex: foca nos impactos econômicos"
                  className="text-xs rounded border bg-input px-3 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
            </div>
          )}

          {/* Publish toggle — shared footer */}
          <div className="border-t px-3 py-2.5 shrink-0">
            <label className="flex items-center gap-2 cursor-pointer group">
              <div
                onClick={() => setPublish((v) => !v)}
                className={cn(
                  "size-4 rounded border-2 shrink-0 flex items-center justify-center transition-colors",
                  publish
                    ? "border-primary bg-primary"
                    : "border-muted-foreground/40 group-hover:border-muted-foreground",
                )}
              >
                {publish && (
                  <svg className="size-2.5 text-white" fill="none" viewBox="0 0 10 8">
                    <path d="M1 4l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              <span
                className="text-xs text-muted-foreground group-hover:text-foreground transition-colors select-none"
                onClick={() => setPublish((v) => !v)}
              >
                Publicar ao gerar
              </span>
            </label>
          </div>
        </div>

        {/* Right — log */}
        <div className="flex-1 flex flex-col overflow-hidden p-6">
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
      </div>
    </div>
  )
}
