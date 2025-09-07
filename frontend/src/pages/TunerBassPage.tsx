// src/pages/TunerBassPage.tsx
import { useEffect, useRef, useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import Gauge from '../components/Gauge'

type BassString = 'E' | 'A' | 'D' | 'G'

// 관찰치 기반 목표(정수 Hz)
const STRING_TARGET: Record<BassString, number> = { E: 41, A: 54.8, D: 36.9, G: 48.9 }

// 게이팅/락/재암 파라미터
const START_MAX_HZ = 150   // 이 값 아래로 들어오면 트래킹 시작 (고조파 무시)
const TRACK_MAX_HZ = 120   // 트래킹 중 이 값 아래만 최소값 갱신
const LOCK_TIME_MS = 1200  // 트래킹 최대 시간 → 초과 시 락
const QUIET_GAP_MS = 200   // 무음으로 간주하는 간격
const MIN_LOCK_HOLD_MS = 120 // 락 직후 최소 유지 시간(튕김 잔향에 의한 바로 재암 방지)

export default function TunerBassPage() {
  const [deviceId, setDeviceId] = useState<string>('')
  const [s, setS] = useState<BassString>('E')
  const target = STRING_TARGET[s]

  // 저음 안정화(필요시 fftSize 16384 / minVolumeRms 0.03)
  const pitch = usePitch(deviceId || undefined, { fftSize: 8192, minVolumeRms: 0.02 })

  type Mode = 'idle' | 'tracking' | 'locked'
  const [mode, setMode] = useState<Mode>('idle')

  // 최소값/락 값
  const minHzRef = useRef<number | null>(null)
  const validMinRef = useRef(false)
  const lockedHzRef = useRef<number | null>(null)

  // 타이밍
  const startMsRef = useRef<number>(0)       // 트래킹 시작 시각
  const lastPitchMsRef = useRef<number>(0)   // 마지막으로 pitch 검출된 시각
  const lockedAtMsRef = useRef<number>(0)    // 락 진입 시각

  // 재암 상태: 락 중 고주파 or 무음 감지 후 true → 다시 <150Hz 들어오면 재시작
  const rearmArmedRef = useRef(false)

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
    mode === 'locked' ? lockedHzRef.current
    : mode === 'tracking' ? minHzRef.current
    : null

  const cents =
    displayHz != null ? 1200 * Math.log2(displayHz / target) : 0

  return (
    <div style={{ padding: 16 }}>
      <h2>🎸 베이스 튜너 (E/A/D/G · 최소Hz·오토-재측정)</h2>

      <div style={{ marginBottom: 10 }}>
        <DeviceSelect value={deviceId} onChange={setDeviceId} />
      </div>

      <div style={{ marginBottom: 14 }}>
        {(['E','A','D','G'] as BassString[]).map(k => (
          <button
            key={k}
            onClick={() => { setS(k); resetAll() }}
            style={{ marginRight: 8, fontWeight: s === k ? 'bold' as const : 'normal' }}
          >
            {k} ({STRING_TARGET[k]} Hz)
          </button>
        ))}
        <button onClick={resetAll} style={{ marginLeft: 8 }}>리셋</button>
      </div>

      {displayHz ? (
        <div style={{ textAlign: 'center' }}>
          <Gauge cents={cents} />
          <div style={{ fontSize: 64, fontWeight: 700, marginTop: 8 }}>{s}</div>
          <div style={{ marginTop: 4 }}>
            {displayHz.toFixed(1)} Hz / {cents > 0 ? '+' : ''}{cents.toFixed(0)} cents
          </div>
          {mode === 'locked' && (
            <div style={{ marginTop: 6, fontSize: 12, color: '#4caf50' }}>locked</div>
          )}
          <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
            목표 {target} Hz 기준 · 정음(±5c)에서 바늘이 초록색
          </div>
        </div>
      ) : (
        <p style={{ marginTop: 24 }}>
          {mode === 'idle' ? '줄을 튕겨주세요.' : '분석 중…'}
        </p>
      )}
    </div>
  )
}