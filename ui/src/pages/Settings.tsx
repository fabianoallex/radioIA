import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Radio, Users, Cpu, Volume2, Download, Bell,
  MessageSquare, Plus, Trash2, Check, RefreshCw, Pencil, X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

// ─── types ──────────────────────────────────────────────────────
interface RadioConfig    { name: string; background_music: string; background_volume_db: number }
interface Narrator       { name: string; voice: string; personality: string }
interface LlmConfig      { model: string; modelos?: { id: string; descricao: string }[] }
interface VinhetaConfig  { voice: string; rate: string }
interface DownloadsConfig{ enabled: boolean; individual: boolean; concatenated: boolean; zip: boolean; mp4: boolean }
interface AnnouncConfig  { enabled: boolean }
interface WelcomeConfig  { falas: string[] }

interface AllSettings {
  radio:         RadioConfig
  narrators:     Narrator[]
  llm:           LlmConfig
  vinheta:       VinhetaConfig
  announcements: AnnouncConfig
  downloads:     DownloadsConfig
  welcome_intro: WelcomeConfig
}

// ─── helpers ────────────────────────────────────────────────────
function SaveButton({ saving, saved, disabled }: { saving: boolean; saved: boolean; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={saving || disabled}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
    >
      {saving ? <RefreshCw className="size-3 animate-spin" /> : saved ? <Check className="size-3" /> : <Check className="size-3" />}
      {saved ? "Salvo ✓" : "Salvar"}
    </button>
  )
}

function useSaved() {
  const [saved, setSaved] = useState(false)
  const markSaved = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }
  return { saved, markSaved }
}

const inputCls = "w-full text-sm rounded border bg-input px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const labelCls = "text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1 block"

// ─── Section wrapper ─────────────────────────────────────────────
function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border bg-card">
      <div className="flex items-center gap-2 px-5 py-3 border-b">
        <Icon className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-medium text-foreground">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

// ─── Radio section ───────────────────────────────────────────────
function RadioSection({ data }: { data: RadioConfig }) {
  const queryClient = useQueryClient()
  const { saved, markSaved } = useSaved()
  const [form, setForm] = useState(data)
  useEffect(() => setForm(data), [data])

  const mutation = useMutation({
    mutationFn: () => api.put("/settings/radio", form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markSaved() },
  })

  return (
    <Section icon={Radio} title="Rádio">
      <form onSubmit={(e) => { e.preventDefault(); mutation.mutate() }} className="space-y-4">
        <div>
          <label className={labelCls}>Nome da rádio</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={inputCls}
          />
          <p className="text-xs text-muted-foreground/60 mt-1">Usado em toda a programação como {"{radio_name}"}</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Música de fundo (caminho)</label>
            <input
              type="text"
              placeholder="ex: assets/bg.mp3 (vazio = sem música)"
              value={form.background_music}
              onChange={(e) => setForm({ ...form, background_music: e.target.value })}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Volume da música de fundo (dB)</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="-40"
                max="0"
                step="1"
                value={form.background_volume_db}
                onChange={(e) => setForm({ ...form, background_volume_db: Number(e.target.value) })}
                className="flex-1 accent-primary"
              />
              <span className="text-sm text-foreground w-12 text-right font-mono">{form.background_volume_db} dB</span>
            </div>
          </div>
        </div>
        <div className="flex justify-end">
          <SaveButton saving={mutation.isPending} saved={saved} />
        </div>
      </form>
    </Section>
  )
}

// ─── Narrators section ───────────────────────────────────────────
function NarratorsSection({ data }: { data: Narrator[] }) {
  const queryClient = useQueryClient()
  const { saved, markSaved } = useSaved()
  const [narrators, setNarrators] = useState<Narrator[]>(data)
  const [editingIdx, setEditingIdx] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<Narrator>({ name: "", voice: "", personality: "" })
  const [addingNew, setAddingNew] = useState(false)
  const [newForm, setNewForm] = useState<Narrator>({ name: "", voice: "", personality: "" })
  useEffect(() => setNarrators(data), [data])

  const mutation = useMutation({
    mutationFn: (next: Narrator[]) => api.put("/settings/narrators", { narrators: next }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markSaved() },
  })

  const save = (next: Narrator[]) => { setNarrators(next); mutation.mutate(next) }

  const narForm = (
    form: Narrator,
    onChange: (f: Narrator) => void,
    onSave: () => void,
    onCancel: () => void,
    isNew: boolean,
  ) => (
    <div className="rounded-md border border-border bg-muted/20 p-3 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Nome</label>
          <input type="text" placeholder="Ana" value={form.name}
            onChange={(e) => onChange({ ...form, name: e.target.value })}
            className="w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Voz edge-tts</label>
          <input type="text" placeholder="pt-BR-ThalitaMultilingualNeural" value={form.voice}
            onChange={(e) => onChange({ ...form, voice: e.target.value })}
            className="w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
        </div>
      </div>
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">Personalidade</label>
        <input type="text" placeholder="descontraída, curiosa e bem-humorada..." value={form.personality}
          onChange={(e) => onChange({ ...form, personality: e.target.value })}
          className="w-full text-xs rounded border bg-input px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel}
          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-border text-muted-foreground hover:text-foreground">
          <X className="size-3" /> Cancelar
        </button>
        <button onClick={onSave} disabled={!form.name || !form.voice}
          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          <Check className="size-3" /> {isNew ? "Adicionar" : "Salvar"}
        </button>
      </div>
    </div>
  )

  return (
    <Section icon={Users} title="Narradores">
      <div className="space-y-2">
        {narrators.map((n, idx) => (
          <div key={idx}>
            {editingIdx === idx ? (
              narForm(
                editForm,
                setEditForm,
                () => { const next = narrators.map((x, i) => i === idx ? editForm : x); save(next); setEditingIdx(null) },
                () => setEditingIdx(null),
                false,
              )
            ) : (
              <div className="flex items-start gap-3 rounded-md border bg-card px-3 py-2.5 group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{n.name}</span>
                    <span className="text-xs font-mono text-muted-foreground">{n.voice}</span>
                    {saved && <span className="text-xs text-emerald-400">✓</span>}
                  </div>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">{n.personality}</p>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => { setEditingIdx(idx); setEditForm({ ...n }) }}
                    className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted">
                    <Pencil className="size-3" />
                  </button>
                  <button onClick={() => save(narrators.filter((_, i) => i !== idx))}
                    className="p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10">
                    <Trash2 className="size-3" />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}

        {addingNew
          ? narForm(newForm, setNewForm,
              () => { save([...narrators, newForm]); setAddingNew(false); setNewForm({ name: "", voice: "", personality: "" }) },
              () => setAddingNew(false), true)
          : (
            <button onClick={() => setAddingNew(true)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors py-1">
              <Plus className="size-3" /> Adicionar narrador
            </button>
          )
        }
      </div>
    </Section>
  )
}

// ─── LLM section ─────────────────────────────────────────────────
function LlmSection({ data }: { data: LlmConfig }) {
  const queryClient = useQueryClient()
  const { saved, markSaved } = useSaved()
  const [model, setModel] = useState(data.model)
  useEffect(() => setModel(data.model), [data])

  const mutation = useMutation({
    mutationFn: () => api.put("/settings/llm", { model }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markSaved() },
  })

  const modelos = data.modelos ?? []

  return (
    <Section icon={Cpu} title="Modelo LLM padrão">
      <div className="space-y-3">
        <div className="space-y-2">
          {modelos.map((m) => (
            <label key={m.id}
              className={cn(
                "flex items-start gap-3 rounded-md border px-3 py-2.5 cursor-pointer transition-colors",
                model === m.id ? "border-primary bg-primary/5" : "border-border hover:bg-muted/30",
              )}>
              <input type="radio" name="llm-model" value={m.id} checked={model === m.id}
                onChange={() => setModel(m.id)} className="mt-0.5 accent-primary" />
              <div>
                <p className="text-sm text-foreground font-mono">{m.id}</p>
                <p className="text-xs text-muted-foreground">{m.descricao}</p>
              </div>
            </label>
          ))}
          {modelos.length === 0 && (
            <input type="text" value={model} onChange={(e) => setModel(e.target.value)} className={inputCls} />
          )}
        </div>
        <div className="flex justify-end">
          <SaveButton saving={mutation.isPending} saved={saved} />
        </div>
      </div>
    </Section>
  )
}

// ─── Vinheta section ─────────────────────────────────────────────
function VinhetaSection({ data }: { data: VinhetaConfig }) {
  const queryClient = useQueryClient()
  const { saved, markSaved } = useSaved()
  const [form, setForm] = useState(data)
  useEffect(() => setForm(data), [data])

  const mutation = useMutation({
    mutationFn: () => api.put("/settings/vinheta", form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markSaved() },
  })

  return (
    <Section icon={Volume2} title="Vinheta">
      <form onSubmit={(e) => { e.preventDefault(); mutation.mutate() }} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Voz edge-tts</label>
            <input type="text" value={form.voice} onChange={(e) => setForm({ ...form, voice: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Velocidade</label>
            <input type="text" placeholder="+20%" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} className={inputCls} />
            <p className="text-xs text-muted-foreground/60 mt-1">Ex: +20%, -10%, +0%</p>
          </div>
        </div>
        <div className="flex justify-end">
          <SaveButton saving={mutation.isPending} saved={saved} />
        </div>
      </form>
    </Section>
  )
}

// ─── Toggle row ──────────────────────────────────────────────────
function Toggle({ label, desc, value, onChange }: { label: string; desc?: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <p className="text-sm text-foreground">{label}</p>
        {desc && <p className="text-xs text-muted-foreground">{desc}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
          value ? "bg-primary" : "bg-muted",
        )}
      >
        <span className={cn(
          "pointer-events-none inline-block size-4 rounded-full bg-white shadow-sm transition-transform",
          value ? "translate-x-4" : "translate-x-0",
        )} />
      </button>
    </div>
  )
}

// ─── Downloads section ───────────────────────────────────────────
function DownloadsSection({ data }: { data: DownloadsConfig }) {
  const queryClient = useQueryClient()
  const { saved, markSaved } = useSaved()
  const [form, setForm] = useState(data)
  useEffect(() => setForm(data), [data])

  const mutation = useMutation({
    mutationFn: () => api.put("/settings/downloads", form),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markSaved() },
  })

  return (
    <Section icon={Download} title="Downloads">
      <div className="divide-y divide-border">
        <Toggle label="Downloads habilitados" value={form.enabled} onChange={(v) => setForm({ ...form, enabled: v })} />
        <Toggle label="Arquivo individual" desc="Download por episódio" value={form.individual} onChange={(v) => setForm({ ...form, individual: v })} />
        <Toggle label="Concatenado" desc="Todos os episódios em um único MP3" value={form.concatenated} onChange={(v) => setForm({ ...form, concatenated: v })} />
        <Toggle label="ZIP" desc="Arquivo ZIP com todos os episódios" value={form.zip} onChange={(v) => setForm({ ...form, zip: v })} />
        <Toggle label="MP4" desc="Vídeo com capa estática (requer ffmpeg)" value={form.mp4} onChange={(v) => setForm({ ...form, mp4: v })} />
      </div>
      <div className="flex justify-end mt-4">
        <SaveButton saving={mutation.isPending} saved={saved} />
      </div>
    </Section>
  )
}

// ─── Announcements + Welcome ─────────────────────────────────────
function MiscSection({ announcements, welcome }: { announcements: AnnouncConfig; welcome: WelcomeConfig }) {
  const queryClient = useQueryClient()
  const { saved: savedA, markSaved: markA } = useSaved()
  const { saved: savedW, markSaved: markW } = useSaved()
  const [annEnabled, setAnnEnabled] = useState(announcements.enabled)
  const [falas, setFalas] = useState<string[]>(welcome.falas ?? [])
  useEffect(() => setAnnEnabled(announcements.enabled), [announcements])
  useEffect(() => setFalas(welcome.falas ?? []), [welcome])

  const mutAnn = useMutation({
    mutationFn: () => api.put("/settings/announcements", { enabled: annEnabled }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markA() },
  })
  const mutWelcome = useMutation({
    mutationFn: () => api.put("/settings/welcome", { falas }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["settings"] }); markW() },
  })

  return (
    <>
      <Section icon={Bell} title="Anúncios entre episódios">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-foreground">Anúncios habilitados</p>
            <p className="text-xs text-muted-foreground">O locutor anuncia o próximo episódio antes de reproduzi-lo</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setAnnEnabled(!annEnabled)}
              className={cn(
                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
                annEnabled ? "bg-primary" : "bg-muted",
              )}
            >
              <span className={cn("pointer-events-none inline-block size-4 rounded-full bg-white shadow-sm transition-transform", annEnabled ? "translate-x-4" : "translate-x-0")} />
            </button>
            <SaveButton saving={mutAnn.isPending} saved={savedA} />
          </div>
        </div>
      </Section>

      <Section icon={MessageSquare} title="Mensagem de boas-vindas">
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">Use <code className="bg-muted px-1 rounded">{"{radio_name}"}</code> para inserir o nome da rádio. Uma fala é escolhida aleatoriamente.</p>
          {falas.map((fala, i) => (
            <div key={i} className="flex items-start gap-2">
              <textarea
                rows={2}
                value={fala}
                onChange={(e) => setFalas(falas.map((f, j) => j === i ? e.target.value : f))}
                className="flex-1 text-xs rounded border bg-input px-2 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none"
              />
              <button
                onClick={() => setFalas(falas.filter((_, j) => j !== i))}
                className="p-1.5 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 mt-0.5"
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
          <button
            onClick={() => setFalas([...falas, ""])}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Plus className="size-3" /> Adicionar variação
          </button>
          <div className="flex justify-end">
            <SaveButton saving={mutWelcome.isPending} saved={savedW} />
          </div>
        </div>
      </Section>
    </>
  )
}

// ─── Page ───────────────────────────────────────────────────────
export default function Settings() {
  const { data, isLoading } = useQuery<AllSettings>({
    queryKey: ["settings"],
    queryFn: () => api.get("/settings"),
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-3xl">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-40 rounded-lg border bg-card animate-pulse" />
        ))}
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl space-y-4">
        <RadioSection     data={data.radio} />
        <NarratorsSection data={data.narrators} />
        <LlmSection       data={data.llm} />
        <VinhetaSection   data={data.vinheta} />
        <DownloadsSection data={data.downloads} />
        <MiscSection      announcements={data.announcements} welcome={data.welcome_intro} />
      </div>
    </div>
  )
}
