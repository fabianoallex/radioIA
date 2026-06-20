import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

interface LogStreamProps {
  lines: string[]
  className?: string
}

function classifyLine(line: string): string {
  const l = line.toLowerCase()
  if (l.includes("[erro") || l.includes("error") || l.includes("traceback") || l.includes("exception"))
    return "text-red-400"
  if (l.startsWith("===") || l.startsWith("---"))
    return "text-zinc-500"
  if (l.includes("concluido") || l.includes("salvo") || l.includes("gerado") || l.includes("[ok]"))
    return "text-emerald-400"
  if (l.includes("gerando") || l.includes("buscando") || l.includes("processando") || l.includes("mixing"))
    return "text-blue-400"
  if (l.includes("[aviso]") || l.includes("aviso") || l.includes("warn"))
    return "text-amber-400"
  if (l.startsWith("  ") || l.startsWith("\t"))
    return "text-zinc-400"
  return "text-zinc-300"
}

export function LogStream({ lines, className }: LogStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [lines])

  return (
    <div className={cn(
      "font-mono text-xs leading-5 overflow-y-auto bg-zinc-950 rounded-lg border p-4",
      className,
    )}>
      {lines.length === 0 ? (
        <span className="text-zinc-600">Aguardando geração...</span>
      ) : (
        lines.map((line, i) => {
          if (line === "[CONCLUIDO]") {
            return (
              <div key={i} className="mt-2 text-emerald-400 font-semibold">
                ✓ Geração concluída
              </div>
            )
          }
          if (line.startsWith("[ERRO")) {
            return (
              <div key={i} className="mt-2 text-red-400 font-semibold">
                ✗ {line}
              </div>
            )
          }
          return (
            <div key={i} className={classifyLine(line)}>
              {line}
            </div>
          )
        })
      )}
      <div ref={bottomRef} />
    </div>
  )
}
