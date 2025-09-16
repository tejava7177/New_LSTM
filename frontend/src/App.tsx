import { useState } from 'react'
import RecordPage from './pages/RecordPage'
import UploadList from './pages/UploadList'
import { Link, useNavigate } from 'react-router-dom'

/** 링크를 버튼처럼 보이게 하는 작은 컴포넌트 */
function ButtonLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      style={{
        display: 'inline-block',
        padding: '6px 10px',
        marginRight: 8,
        border: '1px solid #ccc',
        borderRadius: 6,
        textDecoration: 'none',
        color: '#111',
        background: '#f7f7f7'
      }}
    >
      {children}
    </Link>
  )
}

export default function App() {
  const [tab, setTab] = useState<'record' | 'uploads'>('record')

  return (
    <div style={{ padding: 16 }}>
      <h1>C.B.B – 입력장치 선택 & 녹음 (React)</h1>

      {/* 네비게이션 */}
      <nav style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button
          onClick={() => setTab('record')}
          style={{ fontWeight: tab === 'record' ? 'bold' : 'normal' }}
        >
          🎙 녹음
        </button>

        {/* 기존 베이스 튜너 링크 */}
        <ButtonLink to="/tunerBass">🎸 베이스 튜너</ButtonLink>

        <button
          onClick={() => setTab('uploads')}
          style={{ fontWeight: tab === 'uploads' ? 'bold' : 'normal' }}
        >
          📂 업로드 목록
        </button>

        {/* 새: 코드 진행 생성 페이지로 이동 */}
        <ButtonLink to="/inputBassChord">🎼 코드 진행 생성</ButtonLink>
      </nav>

      {/* 탭 컨텐츠 */}
      {tab === 'record' ? <RecordPage /> : <UploadList />}
    </div>
  )
}