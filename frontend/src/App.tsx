import { useState } from 'react'
import RecordPage from './pages/RecordPage'
import UploadList from './pages/UploadList'

export default function App() {
  const [tab, setTab] = useState<'record' | 'uploads'>('record')

  return (
    <div style={{padding: 16}}>
      <h1>C.B.B – 입력장치 선택 & 녹음 (React)</h1>

      {/* 네비게이션 탭 */}
      <nav style={{marginBottom: 12}}>
        <button onClick={() => setTab('record')}
                style={{marginRight:8, fontWeight: tab==='record'?'bold':'normal'}}>
          🎙 녹음
        </button>
        <button onClick={() => setTab('uploads')}
                style={{fontWeight: tab==='uploads'?'bold':'normal'}}>
          📂 업로드 목록
        </button>
      </nav>

      {/* 페이지 전환 */}
      {tab === 'record' ? <RecordPage /> : <UploadList />}
    </div>
  )
}