// src/pages/TunerBassPage.tsx
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'

type BassString = 'E'|'A'|'D'|'G'

/** 관찰치 기반 목표(정수/소수 Hz) */
const STRING_TARGET: Record<BassString, number> = {
  E: 41.4,
  A: 55.2,
  D: 36.7,
  G: 48.9,
}

// 게이팅/락/재암 파라미터 (기존 값 유지)
const START_MAX_HZ = 150   // 이 값 아래로 들어오면 트래킹 시작 (고조파 무시)
const TRACK_MAX_HZ = 120   // 트래킹 중 이 값 아래만 최소값 갱신
const LOCK_TIME_MS = 1200  // 트래킹 최대 시간 → 초과 시 락
const QUIET_GAP_MS = 200   // 무음으로 간주하는 간격
const MIN_LOCK_HOLD_MS = 120 // 락 직후 최소 유지 시간(즉시 재암 방지)

/** cents 계산 */
const centsBetween = (f: number, ref: number) => 1200 * Math.log2(f / ref)

export default function TunerBassPage() {
  const [deviceId, setDeviceId] = useState<string>('')
  const [armed, setArmed] = useState(false)     // 마이크 권한 여부
  const [s, setS] = useState<BassString>('E')   // 수동 문자열 선택(예전 로직 유지)
  const target = STRING_TARGET[s]


  const pitch = usePitch(deviceId || undefined, { fftSize: 8192, minVolumeRms: 0.02 })

  type Mode = 'idle' | 'tracking' | 'locked'
  const [mode, setMode] = useState<Mode>('idle')

  // 최소값/락 값
  const minHzRef     = useRef<number | null>(null)
  const validMinRef  = useRef(false)
  const lockedHzRef  = useRef<number | null>(null)

  // 타이밍
  const startMsRef     = useRef<number>(0)     // 트래킹 시작 시각
  const lastPitchMsRef = useRef<number>(0)     // 마지막으로 pitch 검출된 시각
  const lockedAtMsRef  = useRef<number>(0)     // 락 진입 시각

  // 재암 상태: 락 중 고주파/무음 감지 후 true → 다시 <150Hz 들어오면 재시작
  const rearmArmedRef  = useRef(false)

  const resetAll = () => {
    setMode('idle')
    minHzRef.current = null
    validMinRef.current = false
    lockedHzRef.current = null
    rearmArmedRef.current = false
    startMsRef.current = 0
  }

  useEffect(() => {
    const now = performance.now()

    if (pitch != null) {
      lastPitchMsRef.current = now

      // ── IDLE: 유효 밴드(<150Hz)로 내려오면 트래킹 시작
      if (mode === 'idle') {
        if (pitch < START_MAX_HZ) {
          setMode('tracking')
          startMsRef.current = now
          minHzRef.current = pitch
          validMinRef.current = pitch < TRACK_MAX_HZ
          rearmArmedRef.current = false
        }
        return
      }

      // ── TRACKING: 저주파(<120Hz)에서만 최소값 갱신. 락 조건 충족 시 락.
      if (mode === 'tracking') {
        if (pitch < TRACK_MAX_HZ) {
          if (minHzRef.current == null || pitch < minHzRef.current) {
            minHzRef.current = pitch
          }
          validMinRef.current = true
        }
        const elapsed = now - startMsRef.current
        if ((pitch > START_MAX_HZ && validMinRef.current) || elapsed >= LOCK_TIME_MS) {
          lockedHzRef.current = validMinRef.current ? (minHzRef.current as number) : null
          if (lockedHzRef.current) {
            setMode('locked')
            lockedAtMsRef.current = now
            rearmArmedRef.current = false
          } else {
            setMode('idle') // 유효 최소가 없으면 리셋
          }
        }
        return
      }

      // ── LOCKED: 재암(arm) → 재시작(restart)
      if (mode === 'locked') {
        const held = now - lockedAtMsRef.current

        // 1) 락 직후 잠깐은 무시(바로 재암 방지)
        if (held < MIN_LOCK_HOLD_MS) return

        // 2) 고주파(>150Hz) 감지되면 재암
        if (pitch > START_MAX_HZ) {
          rearmArmedRef.current = true
          return
        }

        // 3) 재암 상태에서 다시 <150Hz로 내려오면 새 트래킹 시작
        if (rearmArmedRef.current && pitch < START_MAX_HZ) {
          setMode('tracking')
          startMsRef.current = now
          minHzRef.current = pitch
          validMinRef.current = pitch < TRACK_MAX_HZ
          lockedHzRef.current = null
          rearmArmedRef.current = false
        }
        return
      }
    } else {
      // pitch == null (무음/미검출)
      if (mode === 'tracking') {
        // 트래킹 중 무음이면 유효 최소가 있으면 잠시 후 락, 없으면 리셋
        const timer = setTimeout(() => {
          if (performance.now() - lastPitchMsRef.current >= QUIET_GAP_MS) {
            if (validMinRef.current) {
              lockedHzRef.current = minHzRef.current
              setMode(lockedHzRef.current ? 'locked' : 'idle')
              if (lockedHzRef.current) {
                lockedAtMsRef.current = performance.now()
                rearmArmedRef.current = false
              }
            } else {
              resetAll()
            }
          }
        }, QUIET_GAP_MS)
        return () => clearTimeout(timer)
      }

      if (mode === 'locked') {
        // 락 중 무음이면 재암 ON → 다음에 <150Hz 들어오면 자동 재시작
        const timer = setTimeout(() => {
          if (performance.now() - lastPitchMsRef.current >= QUIET_GAP_MS) {
            rearmArmedRef.current = true
          }
        }, QUIET_GAP_MS)
        return () => clearTimeout(timer)
      }
    }
  }, [pitch, mode])

  // 표시 Hz: tracking은 현재까지의 min, locked는 고정값
  const displayHz =
    mode === 'locked'   ? lockedHzRef.current :
    mode === 'tracking' ? minHzRef.current   :
    null

  // 센트/상태
  const cents = displayHz != null ? centsBetween(displayHz, target) : 0
  const visualCents = Math.max(-100, Math.min(100, cents))
  const locked = mode === 'locked'
  const status: 'flat'|'near'|'sharp' =
    visualCents < -6 ? 'flat' : visualCents > 6 ? 'sharp' : 'near'

  return (
    <div className="tb-wrap">
      {/* 헤더 */}
      <header className="tb-header">
        <div className="tb-brand">
          <span className="tb-emoji">🎸</span> 베이스 튜너
          <span className="tb-sub">E / A / D / G</span>
        </div>
        <div className="tb-actions">
          <button
            className="tb-btn"
            onClick={async () => {
              await navigator.mediaDevices.getUserMedia({ audio: true })
              setArmed(true)
            }}
          >
            마이크 권한
          </button>
         <DeviceSelect
          value={deviceId}
          onChange={setDeviceId}
          showPermissionButton={false}
          showRefreshButton={false}
          />
          <button className="tb-btn" onClick={resetAll}>새로고침</button>
        </div>
      </header>

      {/* 본문 카드 */}
      <section className="tb-card">
        {/* 왼쪽: 문자열 선택(수동) */}
        <aside className="tb-side">
          <div className="tb-block">
            <div className="tb-label">문자열 선택</div>
            <div className="tb-chips">
              {(['E','A','D','G'] as BassString[]).map(k => (
                <Chip
                  key={k}
                  active={s === k}
                  onClick={() => { setS(k); resetAll() }}
                >
                  {k} <span className="tb-chip-sub">({STRING_TARGET[k].toFixed(1)} Hz)</span>
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

        {/* 오른쪽: 게이지/읽기/CTA */}
        <div className="tb-gauge">
          <Gauge
            label={s}
            pitch={displayHz ?? 0}
            cents={visualCents}
            status={status}
            locked={locked}
          />

          <div className="tb-readouts">
            <div className="tb-note">
              <div className={`tb-status ${locked ? 'ok' : status}`}>
                {locked ? 'locked' : status === 'near' ? 'near' : status}
              </div>
              <div className="tb-note-name">{s}</div>
              <div className="tb-freq">
                {displayHz != null ? `${displayHz.toFixed(1)} Hz` : '—'}
                <span className="tb-slim"> / </span>
                {target.toFixed(1)} Hz
              </div>
              <div className="tb-cent">
                {visualCents >= 0 ? '+' : ''}{visualCents.toFixed(0)} cents
              </div>
            </div>
          </div>

          <div className="tb-help">
            목표 {target.toFixed(1)} Hz 기준 · {locked ? '정음(±5c 이내)에서 바늘이 초록색' : '바늘이 중앙에 올 때까지 튜닝해 보세요.'}
          </div>

          {/* 다음 단계 CTA */}
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

/* ---------- 소형 구성 요소들 (디자인 유지) ---------- */

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

/** SVG 게이지 — 최신 디자인 유지, 각도/색상은 위 로직(cents/status/locked)로 구동 */
function Gauge({
  label, pitch, cents, status, locked
}: { label: string; pitch: number; cents: number; status: 'flat'|'near'|'sharp'; locked: boolean }) {
  // -50c..+50c → -60deg..+60deg (시각 안정성을 위해 clamp)
  const angle = Math.max(-50, Math.min(50, cents)) * (60/50)
  const stroke = locked ? '#10b981' : (status==='near' ? '#f59e0b' : (status==='sharp' ? '#ef4444' : '#3b82f6'))

  return (
    <svg className="tb-svg" viewBox="0 0 300 220" role="img" aria-label={`tuning gauge for ${label}`}>
      <defs>
        <linearGradient id="ring" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#c7d2fe"/>
          <stop offset="100%" stopColor="#93c5fd"/>
        </linearGradient>
      </defs>

      {/* 반원 트랙 */}
      <path d="M40 170 A110 110 0 0 1 260 170" fill="none" stroke="url(#ring)" strokeWidth="16" strokeLinecap="round" />

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