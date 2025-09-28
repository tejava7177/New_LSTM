// src/App.tsx
import { Outlet } from 'react-router-dom'

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Outlet />
    </div>
  )
}