// src/main.tsx
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App'
import HomePage from './pages/HomePage'
import RecordPage from './pages/RecordPage'
import UploadList from './pages/UploadList'
import PracticeMixPage from './pages/PracticeMixPage'
import TunerPage from './pages/TunerPage'
import TunerBassPage from './pages/TunerBassPage'
import InputBassChordPage from './pages/InputBassChordPage'
import './styles/globals.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<HomePage />} />
          <Route path="tunerBass" element={<TunerBassPage />} />
          <Route path="inputBassChord" element={<InputBassChordPage />} />
          {/* 필요 시 유지되는 기타 페이지들 */}
          <Route path="practice-mix" element={<PracticeMixPage />} />
          <Route path="uploads" element={<UploadList />} />
          <Route path="tuner" element={<TunerPage />} />
          <Route path="record" element={<RecordPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
)