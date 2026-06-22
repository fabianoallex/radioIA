import { useState, useRef, useEffect, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Pencil, Trash2, Check, X, RefreshCw, AlertTriangle, Clock, CheckCircle2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

// ─── types ──────────────────────────────────────────────────────
interface Slot {
  time: string
  label: string
  sources?: string[]
  slot_id?: number | null
  replay_of?: number | null
  date?: string | null
}

interface SlotForm {
  time: string
  label: string
  sources_str: string
  slot_id: string
  replay_of: string
}

interface SourceOption {
  id: string
  name: string
}

type ReplayState = "generated" | "awaiting" | "missing" | null

// ─── helpers ────────────────────────────────────────────────────
function nowHHMM(): string {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
}

function slotToForm(s: Slot): SlotForm {
  return {
    time: s.time,
    label: s.label,
    sources_str: (s.sources ?? []).join(", "),
    slot_id: s.slot_id != null ? String(s.slot_id) : "",
    replay_of: s.replay_of != null ? String(s.replay_of) : "",
  }
}

function formToSlot(f: SlotForm, original?: Slot): Slot {
  const sources = f.sources_str
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
  const slot: Slot = { time: f.time.trim(), label: f.label.trim() }
  if (sources.length) slot.sources = sources
  const sid = parseInt(f.slot_id)
  if (!isNaN(sid)) slot.slot_id = sid
  const rof = parseInt(f.replay_of)
  if (!isNaN(rof)) slot.replay_of = rof
  // preserve date if original had one
  if (original?.date) slot.date = original.date
  return slot
}

function emptyForm(): SlotForm {
  return { time: "", label: "", sources_str: "", slot_id: "", replay_of: "" }
}

function slotColor(s: Slot): string {
  if (s.replay_of != null) return "bg-zinc-600"
  const srcs = (s.sources ?? []).join(" ")
  if (srcs.includes("youtube")) return "bg-blue-500"
  if (srcs.includes("music")) return "bg-purple-500"
  if (srcs.includes("horoscopo")) return "bg-pink-500"
  if (srcs.match(/noticias|rss|tecnologia/)) return "bg-amber-500"
  if (srcs.match(/loteria|copa|clipping|utilidades/)) return "bg-green-500"
  return "bg-primary"
}

function slotBadgeClass(s: Slot): string {
  if (s.replay_of != null) return "bg-zinc-700 text-zinc-400"
  const srcs = (s.sources ?? []).join(" ")
  if (srcs.includes("youtube")) return "bg-blue-500/10 text-blue-400"
  if (srcs.includes("music")) return "bg-purple-500/10 text-purple-400"
  if (srcs.includes("horoscopo")) return "bg-pink-500/10 text-pink-400"
  if (srcs.match(/noticias|rss|tecnologia/)) return "bg-amber-500/10 text-amber-400"
  if (srcs.match(/loteria|copa|clipping/)) return "bg-green-500/10 text-green-400"
  return "bg-primary/10 text-primary"
}

// ─── Timeline strip (horizontal) ────────────────────────────────
function TimelineStrip({ slots, now }: { slots: Slot[]; now: string }) {
  return (
    <div className="relative h-6 bg-zinc-900 rounded border mx-0 overflow-hidden">
      {/* hour grid */}
      {Array.from({ length: 25 }, (_, i) => i).map((h) => (
        <div
          key={h}
          className="absolute top-0 bottom-0 border-l border-zinc-800"
          style={{ left: `${(h / 24) * 100}%` }}
        />
      ))}
      {/* slot marks */}
      {slots.map((s, i) => {
        const [h, m] = s.time.split(":").map(Number)
        const pct = ((h * 60 + m) / (24 * 60)) * 100
        return (
          <div
            key={i}
            className={cn("absolute top-1 bottom-1 w-0.5 rounded-full", slotColor(s))}
            style={{ left: `${pct}%` }}
            title={`${s.time} — ${s.label}`}
          />
        )
      })}
      {/* now indicator */}
      {(() => {
        const [h, m] = now.split(":").map(Number)
        const pct = ((h * 60 + m) / (24 * 60)) * 100
        return (
          <div
            className="absolute top-0 bottom-0 w-px bg-white/70 z-10"
            style={{ left: `${pct}%` }}
          />
        )
      })()}
      {/* hour labels */}
      {[7, 12, 18, 23].map((h) => (
        <span
          key={h}
          className="absolute top-0.5 text-[9px] text-zinc-600 leading-none"
          style={{ left: `${(h / 24) * 100}%`, transform: "translateX(-50%)" }}
        >
          {h}h
        </span>
      ))}
    </div>
  )
}

// ─── Inline edit form ────────────────────────────────────────────
function SlotForm({
  form,
  onChange,
  onSave,
  onCancel,
  saving,
  isNew = false,
  availableSources = [],
  slotsWithId = [],
  suggestedSlotId,
}: {
  form: SlotForm
  onChange: (f: SlotForm) => void
  onSave: () => void
  onCancel: () => void
  saving: boolean
  isNew?: boolean
  availableSources?: SourceOption[]
  slotsWithId?: Slot[]
  suggestedSlotId?: number
}) {
  const inputCls =
    "w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"

  const currentSources = form.sources_str.split(",").map(s => s.trim()).filter(Boolean)

  const toggleSource = (id: string) => {
    const next = currentSources.includes(id)
      ? currentSources.filter(s => s !== id)
      : [...currentSources, id]
    onChange({ ...form, sources_str: next.join(", ") })
  }

  return (
    <div className="grid grid-cols-2 gap-2 p-3 bg-muted/30 rounded-md border border-border/50">
      <div>
        <label className="text-xs text-muted-foreground mb-0.5 block">Horário</label>
        <input
          type="time"
          value={form.time}
          onChange={(e) => onChange({ ...form, time: e.target.value })}
          className={inputCls}
        />
      </div>
      <div>
        <label className="text-xs text-muted-foreground mb-0.5 block">Label</label>
        <input
          type="text"
          placeholder="Nome do slot"
          value={form.label}
          onChange={(e) => onChange({ ...form, label: e.target.value })}
          className={inputCls}
        />
      </div>

      {/* Sources — chips se disponíveis, fallback para input texto */}
      <div className="col-span-2">
        <label className="text-xs text-muted-foreground mb-1 block">Fontes</label>
        {availableSources.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {availableSources.map(src => {
              const active = currentSources.includes(src.id)
              return (
                <button
                  key={src.id}
                  type="button"
                  onClick={() => toggleSource(src.id)}
                  className={cn(
                    "text-xs px-2 py-0.5 rounded border transition-colors",
                    active
                      ? "bg-primary/20 border-primary text-primary"
                      : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
                  )}
                >
                  {src.name || src.id}
                </button>
              )
            })}
          </div>
        ) : (
          <input
            type="text"
            placeholder="youtube, noticias, musica"
            value={form.sources_str}
            onChange={(e) => onChange({ ...form, sources_str: e.target.value })}
            className={inputCls}
          />
        )}
      </div>

      {/* slot_id — somente ao criar novo slot */}
      {isNew && (
        <div>
          <label className="text-xs text-muted-foreground mb-0.5 block">
            slot_id <span className="text-zinc-600">— ID único para replay</span>
          </label>
          <div className="flex gap-1.5 items-center">
            <input
              type="number"
              placeholder="opcional"
              value={form.slot_id}
              onChange={(e) => onChange({ ...form, slot_id: e.target.value })}
              className={cn(inputCls, "flex-1")}
            />
            {suggestedSlotId && !form.slot_id && (
              <button
                type="button"
                onClick={() => onChange({ ...form, slot_id: String(suggestedSlotId) })}
                className="shrink-0 text-xs px-2 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
                title="Usar próximo ID livre"
              >
                #{suggestedSlotId}
              </button>
            )}
          </div>
        </div>
      )}

      {/* replay_of — select de slots com slot_id */}
      <div className={isNew ? "" : "col-span-2"}>
        <label className="text-xs text-muted-foreground mb-0.5 block">replay_of</label>
        {slotsWithId.length > 0 ? (
          <select
            value={form.replay_of}
            onChange={(e) => onChange({ ...form, replay_of: e.target.value })}
            className={cn(inputCls, "cursor-pointer")}
          >
            <option value="">— sem replay —</option>
            {slotsWithId.map(s => (
              <option key={s.slot_id} value={String(s.slot_id)}>
                #{s.slot_id} · {s.time} — {s.label}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="number"
            placeholder="opcional"
            value={form.replay_of}
            onChange={(e) => onChange({ ...form, replay_of: e.target.value })}
            className={inputCls}
          />
        )}
      </div>

      <div className="col-span-2 flex justify-end gap-2 pt-1">
        <button
          onClick={onCancel}
          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="size-3" /> Cancelar
        </button>
        <button
          onClick={onSave}
          disabled={saving || !form.time || !form.label}
          className="flex items-center gap-1 text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? <RefreshCw className="size-3 animate-spin" /> : <Check className="size-3" />}
          Salvar
        </button>
      </div>
    </div>
  )
}

// ─── SlotRow ────────────────────────────────────────────────────
function SlotRow({
  slot,
  isPast,
  isNext,
  replayState,
  episodeGenerated,
  highlighted,
  replayCount,
  onToggleReplays,
  onGoToOriginal,
  onEdit,
  onDelete,
}: {
  slot: Slot
  isPast: boolean
  isNext: boolean
  replayState: ReplayState
  episodeGenerated: boolean
  highlighted: boolean
  replayCount: number
  onToggleReplays?: () => void
  onGoToOriginal?: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const isReplay = slot.replay_of != null
  const originalMissing = replayState === "missing"
  const originalAwaiting = replayState === "awaiting"

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md group transition-colors",
        isNext && "ring-1 ring-primary/50 bg-primary/5",
        isNext && isReplay && originalMissing && "ring-amber-500/50 bg-amber-500/5",
        highlighted && "ring-2 ring-primary/60 bg-primary/10",
        isPast && "opacity-40",
      )}
    >
      {/* Color bar */}
      <div className={cn("w-1 h-8 rounded-full shrink-0", slotColor(slot))} />

      {/* Time */}
      <span className="text-xs font-mono text-muted-foreground w-11 shrink-0">{slot.time}</span>

      {/* Label */}
      <span className={cn("text-sm flex-1 truncate", isPast ? "text-muted-foreground" : "text-foreground")}>
        {slot.label}
      </span>

      {/* Sources / replay badge + episode status */}
      <div className="hidden sm:flex items-center gap-1 shrink-0">
        {isReplay ? (
          <>
            <button
              onClick={(e) => { e.stopPropagation(); onGoToOriginal?.() }}
              disabled={!onGoToOriginal}
              title={onGoToOriginal ? "Ir para o slot original" : undefined}
              className={cn(
                "text-xs px-1.5 py-0.5 rounded transition-colors",
                originalMissing ? "bg-amber-500/15 text-amber-400" : slotBadgeClass(slot),
                onGoToOriginal && "hover:opacity-70 cursor-pointer",
                !onGoToOriginal && "cursor-default",
              )}
            >
              replay:{slot.replay_of}
            </button>
            {replayState === "generated" && (
              <span className="flex items-center gap-0.5 text-xs text-emerald-400">
                <CheckCircle2 className="size-3" />
                episódio gerado
              </span>
            )}
            {originalMissing && (
              <span className="flex items-center gap-0.5 text-xs text-amber-400/80">
                <AlertTriangle className="size-3" />
                original não gerado
              </span>
            )}
            {originalAwaiting && (
              <span className="flex items-center gap-0.5 text-xs text-zinc-400">
                <Clock className="size-3" />
                aguardando original
              </span>
            )}
          </>
        ) : (
          <>
            {(slot.sources ?? []).slice(0, 2).map((s) => (
              <span key={s} className={cn("text-xs px-1.5 py-0.5 rounded truncate max-w-28", slotBadgeClass(slot))}>
                {s}
              </span>
            ))}
            {(slot.sources ?? []).length > 2 && (
              <span className="text-xs text-muted-foreground">+{(slot.sources ?? []).length - 2}</span>
            )}
            {/* indicador de episódio gerado */}
            {episodeGenerated ? (
              <span className="flex items-center gap-0.5 text-xs text-emerald-400 ml-1" title="Episódio gerado">
                <CheckCircle2 className="size-3" />
              </span>
            ) : isPast ? (
              <span className="size-1.5 rounded-full bg-zinc-700 ml-1 shrink-0" title="Sem episódio" />
            ) : null}
          </>
        )}
        {slot.slot_id != null && (
          <span className="flex items-center gap-0.5 ml-1">
            <span className="text-xs text-zinc-600">#{slot.slot_id}</span>
            <button
              onClick={(e) => { e.stopPropagation(); onToggleReplays?.() }}
              className="text-xs text-zinc-500 hover:text-primary px-1 rounded transition-colors"
              title={`${replayCount} replay(s) — ver horários`}
            >
              ↺{replayCount}
            </button>
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          onClick={onEdit}
          className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Editar"
        >
          <Pencil className="size-3" />
        </button>
        <button
          onClick={onDelete}
          className="p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors"
          title="Excluir"
        >
          <Trash2 className="size-3" />
        </button>
      </div>

      {isNext && (
        <span className="text-xs text-primary font-medium shrink-0">← próximo</span>
      )}
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────
export default function Schedule() {
  const queryClient = useQueryClient()
  const [now, setNow] = useState(nowHHMM())
  const [editingIdx, setEditingIdx] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<SlotForm>(emptyForm())
  const [addingNew, setAddingNew] = useState(false)
  const [newForm, setNewForm] = useState<SlotForm>(emptyForm())
  const [highlightedTime, setHighlightedTime]       = useState<string | null>(null)
  const [activeReplayListId, setActiveReplayListId] = useState<number | null>(null)
  const nowRowRef  = useRef<HTMLDivElement>(null)
  const listRef    = useRef<HTMLDivElement>(null)
  const slotRefs   = useRef<Map<number, HTMLDivElement>>(new Map())
  const timeRefs   = useRef<Map<string,  HTMLDivElement>>(new Map())

  // Tick every minute
  useEffect(() => {
    const id = setInterval(() => setNow(nowHHMM()), 60_000)
    return () => clearInterval(id)
  }, [])

  const { data, isLoading } = useQuery<{ slots: Slot[] }>({
    queryKey: ["schedule"],
    queryFn: () => api.get("/schedule"),
    staleTime: 30_000,
  })

  const { data: replayStatus } = useQuery<{ date: string; missing: number[] }>({
    queryKey: ["schedule-replay-status"],
    queryFn: () => api.get("/schedule/replay-status"),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
  const missingReplays = new Set(replayStatus?.missing ?? [])

  const { data: sourcesData } = useQuery<{ id: string; name: string }[]>({
    queryKey: ["sources"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/sources"),
    staleTime: 5 * 60_000,
  })
  const availableSources: SourceOption[] = (sourcesData ?? [])
    .filter((s: { id: string; name: string; enabled?: boolean }) => s.enabled !== false)
    .map((s) => ({ id: s.id, name: s.name }))

  const todayStr = new Date().toISOString().slice(0, 10)

  const { data: todayEpisodes } = useQuery<{ episodios: { horario: string }[] }>({
    queryKey: ["episodes", todayStr],
    queryFn: () => api.get(`/episodes?date=${todayStr}`),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  const generatedTimes = useMemo(
    () => new Set((todayEpisodes?.episodios ?? []).map(ep => ep.horario)),
    [todayEpisodes],
  )

  const slots = data?.slots ?? []
  const visibleSlots = slots
    .map((slot, idx) => ({ slot, idx }))
    .filter(({ slot }) => !slot.date || slot.date >= todayStr)

  const saveMutation = useMutation({
    mutationFn: (next: Slot[]) => api.put("/schedule", { slots: next }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule"] })
      setEditingIdx(null)
      setAddingNew(false)
    },
  })

  const handleUpdate = (idx: number) => {
    const next = slots.map((s, i) => (i === idx ? formToSlot(editForm, s) : s))
    saveMutation.mutate(next)
  }

  const handleAdd = () => {
    const next = [...slots, formToSlot(newForm)]
    saveMutation.mutate(next)
    setNewForm(emptyForm())
  }

  const handleDelete = (idx: number) => {
    if (!confirm(`Excluir slot "${slots[idx].label}" (${slots[idx].time})?`)) return
    const next = slots.filter((_, i) => i !== idx)
    saveMutation.mutate(next)
  }

  const startEdit = (idx: number) => {
    setEditingIdx(idx)
    setEditForm(slotToForm(slots[idx]))
    setAddingNew(false)
  }

  const replaysBySlotId = useMemo(() => {
    const map = new Map<number, Slot[]>()
    for (const { slot } of visibleSlots) {
      if (slot.replay_of != null) {
        const arr = map.get(slot.replay_of) ?? []
        arr.push(slot)
        map.set(slot.replay_of, arr)
      }
    }
    return map
  }, [visibleSlots])

  // Slots que possuem slot_id (elegíveis como original de replay)
  const slotsWithId = useMemo(
    () => visibleSlots.map(v => v.slot).filter(s => s.slot_id != null),
    [visibleSlots],
  )

  // Mapa slot_id → Slot (para lookup rápido do original)
  const slotsBySlotId = useMemo(() => {
    const map = new Map<number, Slot>()
    for (const { slot } of visibleSlots) {
      if (slot.slot_id != null) map.set(slot.slot_id, slot)
    }
    return map
  }, [visibleSlots])

  // Próximo slot_id livre (max + 1)
  const suggestedSlotId = useMemo(() => {
    const ids = slots.filter(s => s.slot_id != null).map(s => s.slot_id as number)
    return ids.length === 0 ? 1 : Math.max(...ids) + 1
  }, [slots])

  const getReplayState = (slot: Slot): ReplayState => {
    if (slot.replay_of == null) return null
    if (generatedTimes.has(slot.time)) return "generated"
    if (!missingReplays.has(slot.replay_of)) return null
    const orig = slotsBySlotId.get(slot.replay_of)
    if (!orig || orig.time > now) return "awaiting"
    return "missing"
  }

  const _highlight = (time: string) => {
    setHighlightedTime(time)
    setTimeout(() => setHighlightedTime(null), 1500)
  }

  const scrollToOriginal = (replayOf: number) => {
    const el = slotRefs.current.get(replayOf)
    if (!el) return
    el.scrollIntoView({ behavior: "smooth", block: "center" })
    const origTime = visibleSlots.find(v => v.slot.slot_id === replayOf)?.slot.time
    if (origTime) _highlight(origTime)
  }

  const scrollToTime = (time: string) => {
    const el = timeRefs.current.get(time)
    if (!el) return
    el.scrollIntoView({ behavior: "smooth", block: "center" })
    _highlight(time)
  }

  // Find "next" slot — primeiro futuro que não seja replay com original ausente
  const nextIdx = visibleSlots.findIndex(({ slot }) =>
    slot.time > now && !(slot.replay_of != null && missingReplays.has(slot.replay_of))
  )

  // Scroll to now-row
  useEffect(() => {
    if (nowRowRef.current) {
      nowRowRef.current.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }, [isLoading])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4 shrink-0 gap-3">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Grade de Programação</h1>
          <p className="text-xs text-muted-foreground">
            {visibleSlots.length} slot(s) · agora {now}
            {saveMutation.isSuccess && (
              <span className="ml-2 text-emerald-400">✓ salvo</span>
            )}
            {saveMutation.isError && (
              <span className="ml-2 text-red-400">✗ erro ao salvar</span>
            )}
          </p>
        </div>
        <button
          onClick={() => {
            setAddingNew(true)
            setEditingIdx(null)
            setNewForm(emptyForm())
            listRef.current?.scrollTo({ top: 0, behavior: "smooth" })
          }}
          className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="size-3.5" />
          Novo slot
        </button>
      </div>

      {/* Timeline strip */}
      <div className="px-6 py-2 border-b shrink-0">
        <TimelineStrip slots={visibleSlots.map(v => v.slot)} now={now} />
      </div>

      {/* List */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-0.5">
        {isLoading ? (
          <div className="space-y-1">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="h-9 rounded-md bg-muted/50 animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {/* Add new form at top if addingNew */}
            {addingNew && (
              <div className="mb-2">
                <SlotForm
                  form={newForm}
                  onChange={setNewForm}
                  onSave={handleAdd}
                  onCancel={() => setAddingNew(false)}
                  saving={saveMutation.isPending}
                  isNew
                  availableSources={availableSources}
                  slotsWithId={slotsWithId}
                  suggestedSlotId={suggestedSlotId}
                />
              </div>
            )}

            {visibleSlots.map(({ slot, idx }, vIdx) => {
              const isPast = slot.time < now && vIdx !== nextIdx - 1
              const isNext = vIdx === nextIdx

              const replaysOf = slot.slot_id != null ? (replaysBySlotId.get(slot.slot_id) ?? []) : []

              return (
                <div
                  key={`${slot.time}-${idx}`}
                  ref={el => {
                    if (!el) return
                    timeRefs.current.set(slot.time, el)
                    if (slot.slot_id != null) slotRefs.current.set(slot.slot_id, el)
                  }}
                >
                  {/* "now" separator */}
                  {isNext && (
                    <div ref={nowRowRef} className="flex items-center gap-2 py-1 my-1">
                      <div className="flex-1 border-t border-white/20" />
                      <span className="text-xs text-white/40 font-mono">{now}</span>
                      <div className="flex-1 border-t border-white/20" />
                    </div>
                  )}

                  <SlotRow
                    slot={slot}
                    isPast={isPast}
                    isNext={isNext}
                    replayState={getReplayState(slot)}
                    episodeGenerated={generatedTimes.has(slot.time)}
                    highlighted={slot.time === highlightedTime}
                    replayCount={replaysOf.length}
                    onToggleReplays={slot.slot_id != null ? () => setActiveReplayListId(id => id === slot.slot_id ? null : slot.slot_id!) : undefined}
                    onGoToOriginal={slot.replay_of != null ? () => scrollToOriginal(slot.replay_of!) : undefined}
                    onEdit={() => startEdit(idx)}
                    onDelete={() => handleDelete(idx)}
                  />

                  {/* Lista de replays do slot original */}
                  {activeReplayListId === slot.slot_id && (
                    <div className="ml-14 mb-1 flex flex-col">
                      {replaysOf.map(r => (
                        <button
                          key={r.time}
                          onClick={() => { scrollToTime(r.time); setActiveReplayListId(null) }}
                          className="text-left text-xs px-2 py-1 rounded flex items-center gap-1.5 text-zinc-400 hover:text-foreground hover:bg-muted transition-colors"
                        >
                          <span className="text-zinc-600">↩</span>
                          {r.time} — {r.label || (r.sources ?? []).join(", ")}
                        </button>
                      ))}
                      <button
                        onClick={() => {
                          setNewForm({ time: "", label: slot.label, sources_str: "", slot_id: "", replay_of: String(slot.slot_id) })
                          setAddingNew(true)
                          setEditingIdx(null)
                          setActiveReplayListId(null)
                          listRef.current?.scrollTo({ top: 0, behavior: "smooth" })
                        }}
                        className="text-left text-xs px-2 py-1 rounded flex items-center gap-1.5 text-primary/60 hover:text-primary hover:bg-primary/5 transition-colors border-t border-border/30 mt-0.5 pt-1.5"
                      >
                        <Plus className="size-3" />
                        Novo replay
                      </button>
                    </div>
                  )}

                  {editingIdx === idx && (
                    <div className="ml-4 mt-1 mb-2">
                      <SlotForm
                        form={editForm}
                        onChange={setEditForm}
                        onSave={() => handleUpdate(idx)}
                        onCancel={() => setEditingIdx(null)}
                        saving={saveMutation.isPending}
                        availableSources={availableSources}
                        slotsWithId={slotsWithId}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </>
        )}
      </div>
    </div>
  )
}
