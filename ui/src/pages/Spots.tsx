import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Plus, Pencil, Trash2, Mic, FileAudio, Sparkles,
  X, Check, ChevronDown, ChevronUp, RefreshCw, Radio,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

// ─── types ──────────────────────────────────────────────────────
type SpotType = "file" | "tts" | "llm"

interface Spot {
  id: string
  type: SpotType
  weight: number
  path?: string
  text?: string
  topic?: string
  duration_seconds?: number
  model?: string
  voice?: string
  rate?: string
}

interface SpotForm {
  id: string
  type: SpotType
  weight: string
  path: string
  text: string
  topic: string
  duration_seconds: string
  model: string
  voice: string
  rate: string
}

interface SpotsConfig {
  fallback_every?: number
  between_episodes_every?: number
}

// ─── helpers ────────────────────────────────────────────────────
function emptyForm(): SpotForm {
  return { id: "", type: "tts", weight: "1", path: "", text: "", topic: "", duration_seconds: "20", model: "", voice: "", rate: "" }
}

function spotToForm(s: Spot): SpotForm {
  return {
    id: s.id,
    type: s.type,
    weight: String(s.weight ?? 1),
    path: s.path ?? "",
    text: s.text ?? "",
    topic: s.topic ?? "",
    duration_seconds: String(s.duration_seconds ?? 20),
    model: s.model ?? "",
    voice: s.voice ?? "",
    rate: s.rate ?? "",
  }
}

function formToSpot(f: SpotForm): Spot {
  const s: Spot = { id: f.id.trim(), type: f.type, weight: parseInt(f.weight) || 1 }
  if (f.type === "file" && f.path) s.path = f.path.trim()
  if (f.type === "tts" && f.text) s.text = f.text.trim()
  if (f.type === "llm") {
    if (f.topic) s.topic = f.topic.trim()
    const dur = parseInt(f.duration_seconds)
    if (!isNaN(dur)) s.duration_seconds = dur
    if (f.model) s.model = f.model.trim()
  }
  if (f.voice) s.voice = f.voice.trim()
  if (f.rate) s.rate = f.rate.trim()
  return s
}

// ─── Type info ──────────────────────────────────────────────────
const TYPE_INFO: Record<SpotType, { label: string; icon: React.ElementType; color: string; desc: string }> = {
  file: { label: "Arquivo", icon: FileAudio, color: "text-blue-400 bg-blue-500/10", desc: "MP3 pré-gravado" },
  tts:  { label: "TTS",     icon: Mic,       color: "text-emerald-400 bg-emerald-500/10", desc: "Texto → voz" },
  llm:  { label: "LLM",     icon: Sparkles,  color: "text-purple-400 bg-purple-500/10", desc: "Gerado por IA" },
}

function TypeBadge({ type }: { type: SpotType }) {
  const info = TYPE_INFO[type]
  const Icon = info.icon
  return (
    <span className={cn("flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium", info.color)}>
      <Icon className="size-3" />
      {info.label}
    </span>
  )
}

// ─── SpotForm component ──────────────────────────────────────────
function SpotFormPanel({
  form,
  onChange,
  onSave,
  onCancel,
  saving,
  isEdit,
}: {
  form: SpotForm
  onChange: (f: SpotForm) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
  isEdit: boolean
}) {
  const inputCls = "w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
  const valid = form.id.trim() && form.type

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">ID do spot</label>
          <input
            type="text"
            placeholder="ex: spot-abertura"
            value={form.id}
            disabled={isEdit}
            onChange={(e) => onChange({ ...form, id: e.target.value })}
            className={cn(inputCls, isEdit && "opacity-50 cursor-not-allowed")}
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Tipo</label>
          <select
            value={form.type}
            onChange={(e) => onChange({ ...form, type: e.target.value as SpotType })}
            className={inputCls}
          >
            <option value="tts">TTS (texto → voz)</option>
            <option value="llm">LLM (IA gera script)</option>
            <option value="file">Arquivo MP3</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Peso</label>
          <input
            type="number"
            min="1"
            max="10"
            value={form.weight}
            onChange={(e) => onChange({ ...form, weight: e.target.value })}
            className={inputCls}
          />
        </div>
      </div>

      {/* Type-specific fields */}
      {form.type === "file" && (
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Caminho do arquivo MP3</label>
          <input
            type="text"
            placeholder="ex: spots/abertura.mp3"
            value={form.path}
            onChange={(e) => onChange({ ...form, path: e.target.value })}
            className={inputCls}
          />
        </div>
      )}

      {form.type === "tts" && (
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Texto para narrar</label>
          <textarea
            rows={3}
            placeholder="Texto que será convertido em áudio via TTS..."
            value={form.text}
            onChange={(e) => onChange({ ...form, text: e.target.value })}
            className={cn(inputCls, "resize-none")}
          />
        </div>
      )}

      {form.type === "llm" && (
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-muted-foreground mb-1 block">Tema / tópico</label>
            <input
              type="text"
              placeholder="ex: Dica de saúde do dia"
              value={form.topic}
              onChange={(e) => onChange({ ...form, topic: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Duração (segundos)</label>
            <input
              type="number"
              min="5"
              max="120"
              value={form.duration_seconds}
              onChange={(e) => onChange({ ...form, duration_seconds: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Modelo LLM (opcional)</label>
            <input
              type="text"
              placeholder="padrão do sistema"
              value={form.model}
              onChange={(e) => onChange({ ...form, model: e.target.value })}
              className={inputCls}
            />
          </div>
        </div>
      )}

      {/* Voice / rate overrides */}
      <details className="text-xs">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground py-1 select-none">
          Voz / velocidade (opcional)
        </summary>
        <div className="grid grid-cols-2 gap-3 mt-2">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Voz edge-tts</label>
            <input
              type="text"
              placeholder="ex: pt-BR-AntonioNeural"
              value={form.voice}
              onChange={(e) => onChange({ ...form, voice: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Velocidade</label>
            <input
              type="text"
              placeholder="ex: +10%"
              value={form.rate}
              onChange={(e) => onChange({ ...form, rate: e.target.value })}
              className={inputCls}
            />
          </div>
        </div>
      </details>

      <div className="flex justify-end gap-2 pt-1 border-t border-border">
        <button
          onClick={onCancel}
          className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="size-3" /> Cancelar
        </button>
        <button
          onClick={onSave}
          disabled={saving || !valid}
          className="flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? <RefreshCw className="size-3 animate-spin" /> : <Check className="size-3" />}
          {isEdit ? "Salvar alterações" : "Criar spot"}
        </button>
      </div>
    </div>
  )
}

// ─── SpotCard ────────────────────────────────────────────────────
function SpotCard({
  spot,
  onEdit,
  onDelete,
}: {
  spot: Spot
  onEdit: () => void
  onDelete: () => void
}) {
  const info = TYPE_INFO[spot.type]
  const Icon = info.icon

  const preview =
    spot.type === "tts"  ? spot.text :
    spot.type === "llm"  ? spot.topic :
    spot.type === "file" ? spot.path :
    ""

  return (
    <div className="rounded-lg border bg-card p-4 flex flex-col gap-3 group">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={cn("rounded-md p-1.5 shrink-0", info.color.split(" ").pop())}>
            <Icon className={cn("size-4", info.color.split(" ")[0])} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{spot.id}</p>
            <p className="text-xs text-muted-foreground">{info.desc}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <TypeBadge type={spot.type} />
          <span className="text-xs text-muted-foreground px-1.5 py-0.5 rounded bg-muted">
            ×{spot.weight}
          </span>
        </div>
      </div>

      {preview && (
        <p className="text-xs text-muted-foreground line-clamp-2 bg-muted/30 rounded px-2 py-1.5 font-mono">
          {preview}
        </p>
      )}

      {spot.type === "llm" && spot.duration_seconds && (
        <p className="text-xs text-muted-foreground">~{spot.duration_seconds}s</p>
      )}

      <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onEdit}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <Pencil className="size-3" /> Editar
        </button>
        <button
          onClick={onDelete}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <Trash2 className="size-3" /> Excluir
        </button>
      </div>
    </div>
  )
}

// ─── SpotsConfig section ─────────────────────────────────────────
function SpotsConfigPanel({ config }: { config: SpotsConfig }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [fallback, setFallback] = useState(String(config.fallback_every ?? 2))
  const [between, setBetween] = useState(String(config.between_episodes_every ?? 3))

  const mutation = useMutation({
    mutationFn: () => api.put("/spots-config", {
      fallback_every: parseInt(fallback),
      between_episodes_every: parseInt(between),
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["spots"] }),
  })

  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-left"
      >
        <div>
          <p className="text-sm font-medium text-foreground">Configuração de rotação</p>
          <p className="text-xs text-muted-foreground">
            fallback a cada {config.fallback_every ?? 2} episódios · entre episódios a cada {config.between_episodes_every ?? 3}
          </p>
        </div>
        {open ? <ChevronUp className="size-4 text-muted-foreground" /> : <ChevronDown className="size-4 text-muted-foreground" />}
      </button>

      {open && (
        <div className="mt-3 pt-3 border-t border-border grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">fallback_every</label>
            <input
              type="number"
              min="1"
              value={fallback}
              onChange={(e) => setFallback(e.target.value)}
              className="w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <p className="text-xs text-zinc-600 mt-0.5">Spot de fallback a cada N episódios</p>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">between_episodes_every</label>
            <input
              type="number"
              min="1"
              value={between}
              onChange={(e) => setBetween(e.target.value)}
              className="w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <p className="text-xs text-zinc-600 mt-0.5">Spot entre episódios a cada N</p>
          </div>
          <div className="col-span-2 flex justify-end">
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {mutation.isPending ? <RefreshCw className="size-3 animate-spin" /> : <Check className="size-3" />}
              Salvar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────
export default function Spots() {
  const queryClient = useQueryClient()
  const [addingNew, setAddingNew] = useState(false)
  const [newForm, setNewForm] = useState<SpotForm>(emptyForm())
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<SpotForm>(emptyForm())

  const { data, isLoading } = useQuery<{ spots: Spot[]; spots_config: SpotsConfig }>({
    queryKey: ["spots"],
    queryFn: () => api.get("/spots"),
    staleTime: 30_000,
  })

  const spots = data?.spots ?? []
  const spotsConfig = data?.spots_config ?? {}

  const createMutation = useMutation({
    mutationFn: (s: Spot) => api.post("/spots", s),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["spots"] })
      setAddingNew(false)
      setNewForm(emptyForm())
    },
  })

  const updateMutation = useMutation({
    mutationFn: (s: Spot) => api.put(`/spots/${s.id}`, s),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["spots"] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/spots/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["spots"] }),
  })

  const handleDelete = (spot: Spot) => {
    if (!confirm(`Excluir spot "${spot.id}"?`)) return
    deleteMutation.mutate(spot.id)
  }

  const startEdit = (spot: Spot) => {
    setEditingId(spot.id)
    setEditForm(spotToForm(spot))
    setAddingNew(false)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Spots</h1>
          <p className="text-sm text-muted-foreground">
            {spots.length} spot(s) configurado(s)
          </p>
        </div>
        <button
          onClick={() => { setAddingNew(true); setEditingId(null); setNewForm(emptyForm()) }}
          className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="size-3.5" />
          Novo spot
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* SpotsConfig */}
        <SpotsConfigPanel config={spotsConfig} />

        {/* New spot form */}
        {addingNew && (
          <SpotFormPanel
            form={newForm}
            onChange={setNewForm}
            onSave={() => createMutation.mutate(formToSpot(newForm))}
            onCancel={() => setAddingNew(false)}
            saving={createMutation.isPending}
            isEdit={false}
          />
        )}

        {/* Spots grid / list */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-32 rounded-lg border bg-card animate-pulse" />
            ))}
          </div>
        ) : spots.length === 0 && !addingNew ? (
          <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
            <Radio className="size-10 text-muted-foreground/30" />
            <p className="text-muted-foreground">Nenhum spot configurado</p>
            <p className="text-xs text-muted-foreground/60 max-w-sm">
              Spots são inseridos automaticamente entre episódios. Crie spots do tipo TTS (texto fixo),
              LLM (IA gera o script diariamente) ou Arquivo (MP3 pré-gravado).
            </p>
            <button
              onClick={() => setAddingNew(true)}
              className="text-xs text-primary hover:underline"
            >
              + Criar primeiro spot
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {spots.map((spot) => (
              <div key={spot.id}>
                {editingId === spot.id ? (
                  <SpotFormPanel
                    form={editForm}
                    onChange={setEditForm}
                    onSave={() => updateMutation.mutate(formToSpot(editForm))}
                    onCancel={() => setEditingId(null)}
                    saving={updateMutation.isPending}
                    isEdit={true}
                  />
                ) : (
                  <SpotCard
                    spot={spot}
                    onEdit={() => startEdit(spot)}
                    onDelete={() => handleDelete(spot)}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
