import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App'
import TunerPage from './pages/TunerPage'
import './styles/globals.css'
import TunerBassPage from "./pages/TunerBassPage";
import InputBassChordPage from "./pages/InputBassChordPage";

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
          <Route path="/" element={<App />} />
          <Route path="/tuner" element={<TunerPage />} />
          <Route path="/tunerBass" element={<TunerBassPage />} />   {/* 추가 */}
          <Route path="*" element={<Navigate to="/" />} />
          <Route path="/inputBassChord" element={<InputBassChordPage />} />
</Routes>
    </BrowserRouter>
  </StrictMode>
)