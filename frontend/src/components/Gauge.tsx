// 간단 반원 게이지 : -50 ~ +50 cents ↔ -45° ~ +45°
export default function Gauge({ cents }: { cents: number }) {
  const clamp = Math.max(-50, Math.min(50, cents))
  const deg = (clamp / 50) * 45

  const color = Math.abs(cents) < 5 ? 'limegreen' : 'orange'

  return (
    <svg width="220" height="120" style={{ overflow: 'visible' }}>
      {/* 배경 눈금 */}
      <path d="M10 100 A100 100 0 0 1 210 100" fill="none" stroke="#555" strokeWidth="6" />
      {/* 포인터 */}
      <line
        x1="110" y1="100"
        x2={110 + 90 * Math.sin((-deg * Math.PI) / 180)}
        y2={100 - 90 * Math.cos((-deg * Math.PI) / 180)}
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
      />
    </svg>
  )
}