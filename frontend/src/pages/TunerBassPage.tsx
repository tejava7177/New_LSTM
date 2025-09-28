// src/pages/TunerBassPage.tsx
import { useEffect, useMemo, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { Link } from 'react-router-dom'

/** 베이스 표준 개방현 기준 주파수 */
const BASE: Record<'E'|'A'|'D'|'G', number> = { E: 41.00, A: 54.80, D: 36.90, G: 48.90 }
const STRINGS: Array<keyof typeof BASE> = ['E','A','D','G']

const log2 = (x: number) => Math.log(x) / Math.LN2
const centsBetween = (f: number, ref: number) => 1200 * log2(f / ref)

/** 주파수에 가장 가까운 ‘같은 음 이름’의 옥타브를 찾아줌 */
function nearestOctaveHz(freq: number, base: number) {
  if (freq <= 0) return base
  // base * 2^k 가 freq에 가장 근접하도록 k를 정수로 고름
  const k = Math.round(log2(freq / base))
  return base * Math.pow(2, k)
}

/** 최근 n개 표본의 표준편차 */
function stdev(values: number[]) {
  if (!values.length) return 999
  const m = values.reduce((a,b)=>a+b,0) / values.length
  const v = values.reduce((a,b)=> a + (b-m)*(b-m), 0) / values.length
  return Math.sqrt(v)
}

export default function TunerBassPage() {
  const [deviceId, setDeviceId] = useState<string>('')
  const [auto, setAuto] = useState(true)               // 자동 문자열 선택
  const [sel, setSel] = useState<'E'|'A'|'D'|'G'>('E') // 수동 선택 시
  const [calib, setCalib] = useState(440)              // 필요 시 캘리브레이션(옵션)
  const [armed, setArmed] = useState(false)            // 마이크 권한 안내

  // 마이크에서 피치 추정 (기존 훅 그대로 사용)
  const pitch = usePitch(deviceId || undefined, { fftSize: 8192, minVolumeRms: 0.02 })

  // 주파수가 있을 때 자동으로 가장 가까운 줄 선택
  const activeString: 'E'|'A'|'D'|'G' = useMemo(() => {
    if (!auto || !pitch) return sel
    let best = 'E' as 'E'|'A'|'D'|'G'
    let bestDiff = Infinity
    for (const s of STRINGS) {
      const ref = nearestOctaveHz(pitch, BASE[s])
      const diff = Math.abs(pitch - ref)
      if (diff < bestDiff) { bestDiff = diff; best = s }
    }
    return best
  }, [auto, sel, pitch])

  // 게이지용 계산
  const refHz = pitch ? nearestOctaveHz(pitch, BASE[activeString]) : BASE[activeString]
  const cents = pitch ? centsBetween(pitch, refHz) : 0
  const centsClamped = Math.max(-100, Math.min(100, cents))

  // 잠김(=안정) 판정: 최근 12개의 표본을 보고 편차가 작고, 중심에서 ±5c 이내
  const recentRef = useRef<number[]>([])
  useEffect(() => {
    if (pitch) {
      const arr = recentRef.current
      arr.push(centsClamped)
      if (arr.length > 12) arr.shift()
    } else {
      recentRef.current = []
    }
  }, [pitch, centsClamped])

  const locked = pitch != null && Math.abs(centsClamped) < 5 && stdev(recentRef.current) < 4
  const status: 'flat'|'near'|'sharp' = centsClamped < -6 ? 'flat' : centsClamped > 6 ? 'sharp' : 'near'

  return (
    <div className="tb-wrap">
      {/* 헤더 */}
      <header className="tb-header">
        <div className="tb-brand">
          <span className="tb-emoji">🎸</span> 베이스 튜너
          <span className="tb-sub">E / A / D / G</span>
        </div>
        <div className="tb-actions">
          <button className="tb-btn"
                  onClick={async () => { await navigator.mediaDevices.getUserMedia({ audio:true }); setArmed(true) }}>
            마이크 권한
          </button>
          <DeviceSelect value={deviceId} onChange={setDeviceId} />
          <button className="tb-btn" onClick={()=>{ recentRef.current=[] }}>
            재측정
          </button>
        </div>
      </header>

      {/* 본문 카드 */}
      <section className="tb-card">
        {/* 왼쪽: 컨트롤 */}
        <aside className="tb-side">
          <div className="tb-block">
            <div className="tb-label">모드</div>
            <div className="tb-chips">
              <Chip active={auto} onClick={()=>setAuto(true)}>자동</Chip>
              <Chip active={!auto} onClick={()=>setAuto(false)}>수동</Chip>
            </div>
          </div>

          <div className="tb-block">
            <div className="tb-label">문자열 선택</div>
            <div className="tb-chips">
              {STRINGS.map(s => (
                <Chip
                  key={s}
                  active={activeString === s}
                  disabled={auto}
                  onClick={()=>!auto && setSel(s)}
                >
                  {s} <span className="tb-chip-sub">({BASE[s].toFixed(1)} Hz)</span>
                </Chip>
              ))}
            </div>
          </div>

          <div className="tb-block tb-hint">
            {armed
              ? <>마이크 입력이 활성화되었습니다. 기타/베이스를 <b>브리지 쪽 픽업</b>으로 살짝 세게 튕겨주세요.</>
              : <>먼저 <b>마이크 권한</b>을 허용해 주세요.</>}
          </div>
        </aside>

        {/* 오른쪽: 게이지 */}
        <div className="tb-gauge">
          <Gauge
            label={activeString}
            pitch={pitch ?? 0}
            cents={centsClamped}
            status={status}
            locked={locked}
          />

          <div className="tb-readouts">
            <div className="tb-note">
              <div className={`tb-status ${locked ? 'ok' : status}`}>
                {locked ? 'locked' : status === 'near' ? 'near' : status}
              </div>
              <div className="tb-note-name">{activeString}</div>
              <div className="tb-freq">{pitch ? `${pitch.toFixed(1)} Hz` : '—'} <span className="tb-slim">/</span> {refHz.toFixed(1)} Hz</div>
              <div className="tb-cent">{centsClamped >= 0 ? '+' : ''}{centsClamped.toFixed(0)} cents</div>
            </div>
          </div>

          <div className="tb-help">
            목표 {refHz.toFixed(1)} Hz 기준 · {locked ? '정음(±5c 이내)에서 바늘이 초록색' : '바늘이 중앙에 올 때까지 튜닝해 보세요.'}
          </div>
          {/* ▼ 추가: 다음 단계 CTA */}
          <div className="tb-cta">
            <Link to="/inputBassChord" className="tb-cta-btn" aria-label="코드 진행 생성으로 이동">
              <span className="tb-cta-emoji">🎼</span>
              코드 진행 생성 & 음원 생성하기
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}

/* ---------- 소형 구성 요소들 ---------- */

function Chip({
  children, active, onClick, disabled
}: { children: React.ReactNode; active?: boolean; onClick?: ()=>void; disabled?: boolean }) {
  return (
    <button
      className={`tb-chip ${active ? 'on' : ''} ${disabled ? 'disabled':''}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

/** SVG 게이지 */
function Gauge({
  label, pitch, cents, status, locked
}: { label: string; pitch: number; cents: number; status: 'flat'|'near'|'sharp'; locked: boolean }) {
  // -50c .. +50c → -60deg .. +60deg
  const angle = Math.max(-50, Math.min(50, cents)) * (60/50)
  const stroke = locked ? '#10b981' : status==='near' ? '#f59e0b' : (status==='sharp' ? '#ef4444' : '#3b82f6')

  return (
    <svg className="tb-svg" viewBox="0 0 300 220" role="img" aria-label="tuning gauge">
      {/* 외곽 반원 */}
      <defs>
        <linearGradient id="ring" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#c7d2fe"/>
          <stop offset="100%" stopColor="#93c5fd"/>
        </linearGradient>
      </defs>

      {/* 반원 트랙 */}
      <path
        d="M40 170 A110 110 0 0 1 260 170"
        fill="none" stroke="url(#ring)" strokeWidth="16" strokeLinecap="round"
      />

      {/* 눈금 */}
      {Array.from({length: 11}).map((_,i)=>{
        const a = -60 + i*12; // -60..60
        const r1 = 110, r2 = i%5===0 ? 90 : 100
        const x1 = 150 + r1 * Math.cos((a-90)*Math.PI/180)
        const y1 = 170 + r1 * Math.sin((a-90)*Math.PI/180)
        const x2 = 150 + r2 * Math.cos((a-90)*Math.PI/180)
        const y2 = 170 + r2 * Math.sin((a-90)*Math.PI/180)
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#d1d5db" strokeWidth={i%5===0?3:2}/>
      })}

      {/* 바늘 */}
      <g transform={`rotate(${angle} 150 170)`}>
        <line x1="150" y1="170" x2="150" y2="70" stroke={stroke} strokeWidth="6" strokeLinecap="round"/>
        <circle cx="150" cy="170" r="8" fill={stroke}/>
      </g>

      {/* 중앙 라벨 */}
      <text x="150" y="205" textAnchor="middle" fontSize="14" fill="#6b7280">
        {pitch ? 'detected' : 'listening…'}
      </text>
    </svg>
  )
}