import React from 'react'

type DialProps = {
  label: string
  value: number
  min: number
  max: number
  step?: number
  defaultValue?: number
  onChange: (v:number)=>void
}
function clamp(v:number, min:number, max:number){ return Math.max(min, Math.min(max, v)) }

export function DialKnob({label, value, min, max, step=0.1, defaultValue, onChange}: DialProps){
  const dialRef = React.useRef<HTMLDivElement | null>(null)
  const startVal = React.useRef(value)
  const startY = React.useRef(0)
  const onDown = (e: React.MouseEvent) => {
    startVal.current = value
    startY.current = e.clientY
    const onMove = (ev: MouseEvent) => {
      const dy = startY.current - ev.clientY
      let v = startVal.current + (max - min) * (dy / 150)
      v = Math.round(v / step) * step
      onChange(clamp(v, min, max))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }
  const onDbl = () => { if (typeof defaultValue === 'number') onChange(defaultValue) }
  const angle = 270 * ((value - min) / (max - min)) - 135
  return (
    <div className="knb" role="slider" aria-valuemin={min} aria-valuemax={max} aria-valuenow={value}>
      <div ref={dialRef} className="dial" onMouseDown={onDown} onDoubleClick={onDbl}
           style={{transform:`rotate(${angle}deg)`}}>
        <div className="indicator" />
      </div>
      <div className="knb-label">
        <div className="t">{label}</div>
        <div className="v">{value.toFixed(1)}</div>
      </div>
      <style>{String.raw`
        .knb { display:inline-flex; flex-direction:column; align-items:center; gap:6px; width:96px }
        .knb .dial {
          width:68px; height:68px; border-radius:50%;
          background: radial-gradient(140% 140% at 30% 30%, #111827, #0b1220);
          border:1px solid #1f2937; position:relative; transition:transform .05s linear;
          box-shadow: inset 0 2px 6px rgba(0,0,0,.35), 0 1px 0 rgba(255,255,255,.04);
          cursor:grab;
        }
        .knb .indicator {
          position:absolute; left:50%; top:6px; width:2px; height:24px; background:#e5e7eb;
          transform:translateX(-50%); border-radius:2px; box-shadow:0 0 0 1px rgba(0,0,0,.25);
        }
        .knb .t { font-size:12px; color:#a3b1c7; text-transform:uppercase; letter-spacing:.06em; }
        .knb .v { font-size:12px; color:#e5e7eb; opacity:.9; }
      `}</style>
    </div>
  )
}
