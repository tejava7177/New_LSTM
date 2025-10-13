// src/pages/HomePage.tsx
import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: '40px 16px',
        background: '#fafafa'
      }}
    >
      <div style={{ width: '100%', maxWidth: 980 }}>
        {/* Title */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <h1 style={{ fontSize: 48, letterSpacing: 2, margin: 0 }}>
            <span style={{ fontWeight: 800 }}>C.B.B</span>
          </h1>
          <div style={{ fontSize: 16, color: '#666', marginTop: 6 }}>
            Create&nbsp;Bass&nbsp;Backing&nbsp;Track
          </div>
        </div>

        {/* Cards */}
        <div
          style={{
            display: 'grid',
            gap: 18,
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            alignItems: 'stretch'
          }}
        >
          {/* Bass Tuner */}
          <Tile
            to="/tunerBass"
            title="베이스 튜너"
            desc="기타/베이스 튜닝을 빠르게 맞추세요."
          >
            <BassIcon />
          </Tile>

          {/* Chord Progression */}
          <Tile
            to="/inputBassChord"
            title="코드 진행 생성"
            desc="베이스 음 입력 → 코드 진행 추천 및 트랙 생성"
          >
            <ChordIcon />
          </Tile>
        </div>
      </div>
    </main>
  )
}

/* ---------- 작은 프리미티브 ---------- */

function Tile({
  to,
  title,
  desc,
  children,
}: {
  to: string
  title: string
  desc?: string
  children?: React.ReactNode
}) {
  return (
    <Link
      to={to}
      style={{
        display: 'block',
        border: '1px solid #e7e7e7',
        borderRadius: 16,
        padding: 20,
        textDecoration: 'none',
        color: '#111',
        background: '#fff',
        boxShadow: '0 1px 0 rgba(0,0,0,0.03)',
        transition: 'transform .15s ease, box-shadow .15s ease'
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.boxShadow =
          '0 8px 24px rgba(0,0,0,0.08)'
        ;(e.currentTarget as HTMLAnchorElement).style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.boxShadow =
          '0 1px 0 rgba(0,0,0,0.03)'
        ;(e.currentTarget as HTMLAnchorElement).style.transform = 'translateY(0)'
      }}
      aria-label={title}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: 16 }}>
        <div
          style={{
            display: 'grid',
            placeItems: 'center',
            background: '#f3f6ff',
            border: '1px solid #e0e8ff',
            borderRadius: 12,
            width: 92,
            height: 92
          }}
        >
          {children}
        </div>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>{title}</div>
          {desc && <div style={{ fontSize: 14, color: '#666' }}>{desc}</div>}
        </div>
      </div>
    </Link>
  )
}

/* ---------- 심플한 내장 아이콘 (원하면 이미지로 교체하세요) ---------- */

function BassIcon() {
  return (
    <svg width="54" height="54" viewBox="0 0 64 64" fill="none">
      <rect x="9" y="28" width="34" height="8" rx="4" fill="#3b82f6" />
      <circle cx="48" cy="32" r="8" fill="#1d4ed8" />
      <circle cx="48" cy="32" r="3" fill="white" />
      <rect x="13" y="18" width="6" height="6" rx="3" fill="#93c5fd" />
      <rect x="13" y="40" width="6" height="6" rx="3" fill="#93c5fd" />
    </svg>
  )
}

function ChordIcon() {
  return (
    <svg width="54" height="54" viewBox="0 0 64 64" fill="none">
      <rect x="10" y="14" width="44" height="36" rx="6" fill="#10b981" />
      <rect x="15" y="20" width="34" height="4" rx="2" fill="white" />
      <rect x="15" y="28" width="34" height="4" rx="2" fill="white" />
      <rect x="15" y="36" width="22" height="4" rx="2" fill="white" />
    </svg>
  )
}