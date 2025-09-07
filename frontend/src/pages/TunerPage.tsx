// src/pages/TunerPage.tsx
import { useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { noteFromFreq, centsOff } from '../utils/noteUtils'
import Gauge from '../components/Gauge'

export default function TunerPage() {
  const [deviceId, setDeviceId] = useState<string>()
  const pitch = usePitch(deviceId)
  const note = pitch ? noteFromFreq(pitch) : null
  const cents = pitch && note ? centsOff(pitch, note.freq) : 0

  return (
    <div style={{ padding: 16 }}>
      <h2>🎸 튜너</h2>
      <DeviceSelect value={deviceId || ''} onChange={setDeviceId} />

      {pitch ? (
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          {/* 게이지 */}
          <Gauge cents={cents} />

          {/* 텍스트 */}
          <div style={{ fontSize: 64, fontWeight: 700 }}>{note.name}</div>
          <div>{pitch.toFixed(1)} Hz / {cents > 0 ? '+' : ''}{cents.toFixed(0)} cents</div>
        </div>
      ) : (
        <p style={{ marginTop: 24 }}>입력 신호를 감지 중…</p>
      )}
    </div>
  )

}