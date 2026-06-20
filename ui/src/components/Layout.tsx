import { NavLink, Outlet } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  LayoutDashboard,
  Zap,
  Radio,
  CalendarDays,
  Headphones,
  Megaphone,
  Settings,
  ExternalLink,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"

const NAV = [
  { to: "/",         icon: LayoutDashboard, label: "Dashboard",    end: true },
  { to: "/generator",icon: Zap,             label: "Gerador"              },
  { to: "/sources",  icon: Radio,           label: "Fontes"               },
  { to: "/schedule", icon: CalendarDays,    label: "Grade"                },
  { to: "/episodes", icon: Headphones,      label: "Episódios"            },
  { to: "/spots",    icon: Megaphone,       label: "Spots"                },
  { to: "/settings", icon: Settings,        label: "Configurações"        },
]

export default function Layout() {
  const { data: rtConfig } = useQuery<{ player_url: string; radio_name: string }>({
    queryKey: ["runtime-config"],
    queryFn: () => api.get("/config"),
    staleTime: Infinity,
  })

  const playerUrl = rtConfig?.player_url ?? "http://localhost:5000"
  const radioName = rtConfig?.radio_name ?? "RadioIA"

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <aside className="flex w-56 shrink-0 flex-col border-r bg-sidebar border-sidebar-border">
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
          <Radio className="size-5 text-primary" />
          <span className="font-semibold text-sidebar-foreground tracking-tight">{radioName}</span>
          <span className="ml-auto text-xs text-muted-foreground">admin</span>
        </div>

        <nav className="flex flex-col gap-0.5 p-2 flex-1">
          {NAV.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-sidebar-border p-2">
          <a
            href={playerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground transition-colors"
          >
            <Headphones className="size-4 shrink-0" />
            Abrir player
            <ExternalLink className="size-3 ml-auto text-muted-foreground" />
          </a>
        </div>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden bg-background">
        <Outlet />
      </main>
    </div>
  )
}
