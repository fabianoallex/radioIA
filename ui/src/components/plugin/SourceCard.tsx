import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Rss, Music, Layers, PlayCircle, BarChart2, Newspaper,
  TrendingUp, MessageSquare, Star, BookOpen, Utensils,
  Film, Book, HelpCircle, Link, Mic, MessageCircle,
  Award, Package, Settings, Radio, Clock,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

const ICON_MAP: Record<string, React.ElementType> = {
  youtube:        PlayCircle,
  rss:            Rss,
  music:          Music,
  layers:         Layers,
  "bar-chart-2":  BarChart2,
  "trending-up":  TrendingUp,
  newspaper:      Newspaper,
  "message-square": MessageSquare,
  star:           Star,
  "book-open":    BookOpen,
  utensils:       Utensils,
  film:           Film,
  book:           Book,
  "help-circle":  HelpCircle,
  link:           Link,
  mic:            Mic,
  "message-circle": MessageCircle,
  award:          Award,
  package:        Package,
  radio:          Radio,
}

function PluginIcon({ icon, className }: { icon: string; className?: string }) {
  const Icon = ICON_MAP[icon] ?? Package
  return <Icon className={className} />
}

interface PluginInfo {
  name: string
  icon: string
  description: string
  has_metadata: boolean
  config_schema: unknown[]
}

interface Source {
  id: string
  name: string
  type: string
  enabled: boolean
  plugin_info: PluginInfo
}

const MAX_VISIBLE_SLOTS = 6

interface SourceCardProps {
  source: Source
  onConfigure: (source: Source) => void
  slots?: string[]
}

export function SourceCard({ source, onConfigure, slots }: SourceCardProps) {
  const queryClient = useQueryClient()

  const toggleMutation = useMutation({
    mutationFn: () => api.post(`/sources/${source.id}/toggle`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
  })

  const enabled = source.enabled ?? true

  return (
    <div className={cn(
      "rounded-lg border bg-card p-4 flex flex-col gap-3 transition-opacity",
      !enabled && "opacity-60",
    )}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="rounded-md bg-primary/10 p-1.5 shrink-0">
            <PluginIcon icon={source.plugin_info.icon} className="size-4 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{source.name}</p>
            <p className="text-xs text-muted-foreground">{source.type}</p>
          </div>
        </div>

        {/* Toggle switch */}
        <button
          onClick={() => toggleMutation.mutate()}
          disabled={toggleMutation.isPending}
          className={cn(
            "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200",
            "focus-visible:outline-none disabled:opacity-50",
            enabled ? "bg-primary" : "bg-muted",
          )}
          aria-label={enabled ? "Desabilitar" : "Habilitar"}
        >
          <span className={cn(
            "pointer-events-none inline-block size-4 rounded-full bg-white shadow-sm transition-transform duration-200",
            enabled ? "translate-x-4" : "translate-x-0",
          )} />
        </button>
      </div>

      {/* Horários na grade */}
      <div className="min-h-[1.75rem]">
        {slots && slots.length > 0 ? (
          <div className="flex items-center gap-1 flex-wrap">
            <Clock className="size-3 text-muted-foreground shrink-0" />
            {slots.slice(0, MAX_VISIBLE_SLOTS).map((t) => (
              <span
                key={t}
                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground leading-none"
              >
                {t}
              </span>
            ))}
            {slots.length > MAX_VISIBLE_SLOTS && (
              <span className="text-[10px] text-muted-foreground">
                +{slots.length - MAX_VISIBLE_SLOTS}
              </span>
            )}
          </div>
        ) : (
          <span className="text-[10px] text-muted-foreground/50 italic">
            Não agendado
          </span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <span className={cn(
          "text-xs px-1.5 py-0.5 rounded-sm font-medium",
          enabled
            ? "bg-emerald-500/10 text-emerald-400"
            : "bg-zinc-700/50 text-zinc-500",
        )}>
          {enabled ? "ativa" : "desativada"}
        </span>

        <button
          onClick={() => onConfigure(source)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <Settings className="size-3" />
          Configurar
        </button>
      </div>
    </div>
  )
}

// Card para plugins disponíveis (não configurados)
interface PluginType {
  type: string
  name: string
  description: string
  icon: string
  credentials: string[]
  configured: boolean
  source: string
}

interface AvailablePluginCardProps {
  plugin: PluginType
  onAdd: (plugin: PluginType) => void
}

export function AvailablePluginCard({ plugin, onAdd }: AvailablePluginCardProps) {
  return (
    <div className="rounded-lg border bg-card p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="rounded-md bg-muted p-1.5 shrink-0">
          <PluginIcon icon={plugin.icon} className="size-4 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">{plugin.name}</p>
          <p className="text-xs text-muted-foreground">{plugin.type}</p>
        </div>
        <span className="ml-auto text-xs px-1.5 py-0.5 rounded-sm bg-muted text-muted-foreground">
          {plugin.source === "builtin" ? "built-in" : "plugin"}
        </span>
      </div>

      {plugin.description && (
        <p className="text-xs text-muted-foreground line-clamp-2">{plugin.description}</p>
      )}

      {plugin.credentials.length > 0 && (
        <p className="text-xs text-amber-500/80">
          Requer: {plugin.credentials.join(", ")}
        </p>
      )}

      <button
        onClick={() => onAdd(plugin)}
        className="mt-auto text-xs text-primary hover:text-primary/80 transition-colors text-left"
      >
        + Adicionar fonte
      </button>
    </div>
  )
}
