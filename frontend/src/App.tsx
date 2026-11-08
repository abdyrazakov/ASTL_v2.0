import { Navigate, Route, Routes } from 'react-router-dom'
import { AppStateProvider } from './state/AppState'
import { EditorPage } from './pages/EditorPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { IntersectionEditorPage } from './pages/IntersectionEditorPage'
import { SimulationPage } from './pages/SimulationPage'

export default function App() {
  return (
    <AppStateProvider>
      <div className="h-full flex flex-col">
        <Routes>
          <Route path="/" element={<Navigate to="/editor" replace />} />
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/intersection" element={<IntersectionEditorPage />} />
          <Route path="/simulation" element={<SimulationPage />} />
          <Route path="*" element={<Navigate to="/editor" replace />} />
        </Routes>
      </div>
    </AppStateProvider>
  )
}
