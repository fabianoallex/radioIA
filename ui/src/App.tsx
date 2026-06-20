import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import Layout from "@/components/Layout"
import Dashboard from "@/pages/Dashboard"
import Generator from "@/pages/Generator"
import Sources from "@/pages/Sources"
import Schedule from "@/pages/Schedule"
import Episodes from "@/pages/Episodes"
import Spots from "@/pages/Spots"
import Settings from "@/pages/Settings"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="generator" element={<Generator />} />
            <Route path="sources" element={<Sources />} />
            <Route path="schedule" element={<Schedule />} />
            <Route path="episodes" element={<Episodes />} />
            <Route path="spots" element={<Spots />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
