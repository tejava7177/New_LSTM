// src/main.tsx
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

import HomePage from './pages/HomePage'            // 메인(타이틀 + 두 카드)
import TunerBassPage from './pages/TunerBassPage'
import InputBassChordPage from './pages/InputBassChordPage'
import PracticeMixPage from './pages/PracticeMixPage'
import './styles/globals.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/tunerBass" element={<TunerBassPage />} />
        <Route path="/inputBassChord" element={<InputBassChordPage />} />
        <Route path="/practice-mix" element={<PracticeMixPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
)