import { useState, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { Rss, ExternalLink, Search, ChevronDown, ChevronRight, AlertCircle } from "lucide-react"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

interface FeedItem {
  title: string
  url: string
  published_at: string | null
  summary: string
}

interface FeedPreview {
  feed_title: string
  feed_description: string
  feed_link: string
  total: number
  items: FeedItem[]
}

interface SourceFeeds {
  source_id: string
  source_name: string
  enabled: boolean
  feeds: { name: string; url: string }[]
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return null
  }
}

export default function RssPreview() {
  const [url, setUrl] = useState("")
  const [activeUrl, setActiveUrl] = useState("")
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const inputRef = useRef<HTMLInputElement>(null)

  const { data: sources = [] } = useQuery<SourceFeeds[]>({
    queryKey: ["rss-feeds"],
    queryFn: () => api.get<SourceFeeds[]>("/rss/feeds"),
  })

  const {
    data: preview,
    isLoading,
    isError,
    error,
  } = useQuery<FeedPreview>({
    queryKey: ["rss-preview", activeUrl],
    queryFn: () =>
      api.get<FeedPreview>(`/rss/preview?url=${encodeURIComponent(activeUrl)}`),
    enabled: !!activeUrl,
    retry: false,
  })

  function loadFeed(feedUrl: string) {
    setUrl(feedUrl)
    setActiveUrl(feedUrl)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = url.trim()
    if (trimmed) setActiveUrl(trimmed)
  }

  function toggleSource(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center border-b px-6 py-4 shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Visualizador RSS</h1>
          <p className="text-sm text-muted-foreground">
            Pré-visualize feeds para avaliar a qualidade do conteúdo
          </p>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: feeds configurados */}
        <aside className="w-56 shrink-0 border-r overflow-y-auto bg-sidebar">
          <div className="p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-2 mb-2">
              Feeds configurados
            </p>
            {sources.length === 0 && (
              <p className="text-xs text-muted-foreground px-2">Nenhum feed RSS encontrado</p>
            )}
            {sources.map((src) => {
              const isExpanded = expanded.has(src.source_id)
              return (
                <div key={src.source_id} className="mb-0.5">
                  <button
                    onClick={() => toggleSource(src.source_id)}
                    className="flex items-center gap-1.5 w-full px-2 py-1.5 rounded-md text-sm hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground transition-colors text-left"
                  >
                    {isExpanded ? (
                      <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
                    )}
                    <span
                      className={cn(
                        "truncate font-medium text-sidebar-foreground",
                        !src.enabled && "opacity-40"
                      )}
                    >
                      {src.source_name}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground shrink-0">
                      {src.feeds.length}
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="ml-3 mt-0.5 space-y-0.5 border-l border-sidebar-border pl-2">
                      {src.feeds.map((feed) => (
                        <button
                          key={feed.url}
                          onClick={() => loadFeed(feed.url)}
                          title={feed.url}
                          className={cn(
                            "flex items-center gap-1.5 w-full px-2 py-1.5 rounded-md text-xs transition-colors text-left",
                            activeUrl === feed.url
                              ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                              : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
                          )}
                        >
                          <Rss className="size-3 shrink-0 text-muted-foreground" />
                          <span className="truncate">{feed.name || feed.url}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </aside>

        {/* Área principal */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* URL bar */}
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 px-4 py-3 border-b shrink-0"
          >
            <div className="relative flex-1">
              <Rss className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <input
                ref={inputRef}
                type="url"
                placeholder="https://exemplo.com/feed/rss"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="w-full pl-8 pr-3 py-2 text-sm rounded-md border bg-input text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <button
              type="submit"
              disabled={!url.trim() || isLoading}
              className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors shrink-0"
            >
              <Search className="size-3.5" />
              Carregar
            </button>
          </form>

          {/* Conteúdo */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* Estado inicial */}
            {!activeUrl && (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                <Rss className="size-8 opacity-20" />
                <p className="text-sm">Selecione um feed no painel ou cole uma URL acima</p>
              </div>
            )}

            {/* Loading */}
            {activeUrl && isLoading && (
              <>
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="rounded-lg border bg-card p-4 h-28 animate-pulse" />
                ))}
              </>
            )}

            {/* Erro */}
            {activeUrl && isError && (
              <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                <AlertCircle className="size-4 shrink-0 mt-0.5" />
                <span>{(error as Error).message || "Erro ao carregar o feed"}</span>
              </div>
            )}

            {/* Resultado */}
            {preview && (
              <>
                {/* Cabeçalho do feed */}
                <div className="rounded-lg border bg-card px-4 py-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground truncate">
                      {preview.feed_title || activeUrl}
                    </p>
                    {preview.feed_description && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {preview.feed_description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-muted-foreground">
                      {preview.total} item(s)
                    </span>
                    {preview.feed_link && (
                      <a
                        href={preview.feed_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ExternalLink className="size-3.5" />
                      </a>
                    )}
                  </div>
                </div>

                {/* Itens */}
                {preview.items.map((item, i) => (
                  <div key={i} className="rounded-lg border bg-card p-4 space-y-1.5">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-sm font-medium text-foreground leading-snug">
                        {item.title}
                      </h3>
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors mt-0.5"
                        >
                          <ExternalLink className="size-3.5" />
                        </a>
                      )}
                    </div>
                    {item.published_at && (
                      <p className="text-xs text-muted-foreground">
                        {formatDate(item.published_at)}
                      </p>
                    )}
                    {item.summary && (
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {item.summary}
                      </p>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
