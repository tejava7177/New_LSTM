import { useEffect, useRef, useState } from 'react'

type Props = {
  /** 현재 음의 오차(cents). 음이 낮으면 음수, 높으면 양수. */
  cents: number | null
  /** 중앙(정음) 임계값. 기본 ±5 cents 이내 초록색 */
  inTuneThreshold?: number
}

/** 반원 게이지: -50~+50 cents ↔ -45°~+45° */
export default function Gauge({ cents, inTuneThreshold = 5 }: Props) {
  // 시각적 떨림을 줄이기 위한 저역 통과 필터(지수 이동 평균)
  const [smoothed, setSmoothed] = useState(0)
  const targetRef = useRef(0)
  const rafRef = useRef<number>()

  // 입력 cents를 -50~+50로 클램프
  const clamp = (v: number) => Math.max(-50, Math.min(50, v))
  const target = cents == null ? 0 : clamp(cents)
  targetRef.current = target

  // 애니메이션(보간): 매 프레임 target 쪽으로 조금씩 이동
  useEffect(() => {
    const alpha = 0.18 // 0~1 (값이 작을수록 더 부드러움)
    const tick = () => {
      setSmoothed(prev => prev + alpha * (targetRef.current - prev))
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current!)
  }, [])

  // 각도 변환: -50→-45°, 0→0°, +50→+45°
  const deg = (smoothed / 50) * 45

  // 색상: 정음(±inTune) 초록, 살짝 어긋남 노랑, 크게 어긋남 주황/빨강
  const abs = Math.abs(smoothed)
  const color =
    abs <= inTuneThreshold ? 'limegreen' :
    abs <= 12 ? '#d6a100' :  // 노랑
    abs <= 25 ? 'orange' :
    '#ff5555'

  return (
    <div style={{ display: 'inline-block', textAlign: 'center' }}>
      <svg width="260" height="140" viewBox="0 0 260 140" style={{ overflow: 'visible' }}>
        {/* 반원 배경 */}
        <path d="M20 120 A100 100 0 0 1 240 120" fill="none" stroke="#555" strokeWidth="8" strokeLinecap="round" />
        {/* 중심 눈금(0c) */}
        <line x1="130" y1="120" x2="130" y2="32" stroke="#888" strokeWidth="3" />
        {/* 좌/우 가이드 눈금(±10, ±20, ±30, ±40, ±50 근사) */}
        {[-40,-30,-20,-10,10,20,30,40].map(c => {
          const a = (c / 50) * 45 * (Math.PI / 180)
          const x1 = 130 + 92 * Math.sin(-a)
          const y1 = 120 - 92 * Math.cos(-a)
          const x2 = 130 + 78 * Math.sin(-a)
          const y2 = 120 - 78 * Math.cos(-a)
          return <line key={c} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#777" strokeWidth="3" />
        })}
        {/* 바늘(부드럽게 이동) */}
        <g style={{ transformOrigin: '130px 120px', transform: `rotate(${deg}deg)`, transition: 'transform 40ms linear' }}>
          <line x1="130" y1="120" x2="130" y2="36" stroke={color} strokeWidth="8" strokeLinecap="round" />
        </g>
      </svg>
    </div>
  )
}