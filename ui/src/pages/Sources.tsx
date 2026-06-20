import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Radio, Search } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import { SourceCard, AvailablePluginCard } from "@/components/plugin/SourceCard"

type Tab = "ativas" | "desativadas" | "disponiveis"

interface Source {
  id: string
  name: string
  type: string
  enabled: boolean
  plugin_info: {
    name: string
    icon: string
    description: string
    has_metadata: boolean
    config_schema: unknown[]
  }
}

interface PluginType {
  type: string
  name: string
  description: string
  icon: string
  credentials: string[]
  configured: boolean
  source: string
}

export default function Sources() {
  const [tab, setTab] = useState<Tab>("ativas")
  const [search, setSearch] = useState("")
  const [_configuringSource, setConfiguringSource] = useState<Source | null>(null)

  const { data: sources = [], isLoading: loadingSources } = useQuery<Source[]>({
    queryKey: ["sources"],
    queryFn: () => api.get<Source[]>("/sources"),
  })

  const { data: plugins = [], isLoading: loadingPlugins } = useQuery<PluginType[]>({
    queryKey: ["plugins"],
    queryFn: () => api.get<PluginType[]>("/plugins"),
    enabled: tab === "disponiveis",
  })

  const active   = sources.filter((s) => s.enabled !== false)
  const inactive = sources.filter((s) => s.enabled === false)

  const filteredActive = search
    ? active.filter((s) =>
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.type.toLowerCase().includes(search.toLowerCase())
      )
    : active

  const filteredInactive = search
    ? inactive.filter((s) =>
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.type.toLowerCase().includes(search.toLowerCase())
      )
    : inactive

  const filteredPlugins = search
    ? plugins.filter((p) =>
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.type.toLowerCase().includes(search.toLowerCase())
      )
    : plugins

  const TABS: { id: Tab; label: string; count: number }[] = [
    { id: "ativas",      label: "Ativas",      count: active.length   },
    { id: "desativadas", label: "Desativadas",  count: inactive.length },
    { id: "disponiveis", label: "Disponíveis",  count: plugins.length  },
  ]

  const isLoading = tab === "disponiveis" ? loadingPlugins : loadingSources

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Fontes</h1>
          <p className="text-sm text-muted-foreground">
            {sources.length} fonte(s) configurada(s)
          </p>
        </div>
      </div>

      {/* Tabs + Search */}
      <div className="border-b px-6 shrink-0">
        <div className="flex items-center gap-6">
          <div className="flex">
            {TABS.map(({ id, label, count }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={cn(
                  "relative px-1 py-3 text-sm font-medium transition-colors mr-6",
                  tab === id
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
                <span className={cn(
                  "ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-normal",
                  tab === id ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground",
                )}>
                  {count}
                </span>
                {tab === id && (
                  <span className="absolute inset-x-0 bottom-0 h-0.5 bg-primary rounded-full" />
                )}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2 mb-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Filtrar..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-sm rounded-md border bg-input text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring w-48"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="grid grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="rounded-lg border bg-card p-4 h-28 animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {tab === "ativas" && (
              <>
                {filteredActive.length === 0 ? (
                  <EmptyState icon={Radio} text="Nenhuma fonte ativa" />
                ) : (
                  <div className="grid grid-cols-3 gap-4">
                    {filteredActive.map((s) => (
                      <SourceCard
                        key={s.id}
                        source={s}
                        onConfigure={setConfiguringSource}
                      />
                    ))}
                  </div>
                )}
              </>
            )}

            {tab === "desativadas" && (
              <>
                {filteredInactive.length === 0 ? (
                  <EmptyState icon={Radio} text="Nenhuma fonte desativada" />
                ) : (
                  <div className="grid grid-cols-3 gap-4">
                    {filteredInactive.map((s) => (
                      <SourceCard
                        key={s.id}
                        source={s}
                        onConfigure={setConfiguringSource}
                      />
                    ))}
                  </div>
                )}
              </>
            )}

            {tab === "disponiveis" && (
              <div className="grid grid-cols-3 gap-4">
                {filteredPlugins.map((p) => (
                  <AvailablePluginCard
                    key={p.type}
                    plugin={p}
                    onAdd={() => {
                      /* TODO Fase 2b: abrir formulário de nova fonte */
                    }}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function EmptyState({
  icon: Icon,
  text,
}: {
  icon: React.ElementType
  text: string
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
      <Icon className="size-8 opacity-30" />
      <p className="text-sm">{text}</p>
    </div>
  )
}
