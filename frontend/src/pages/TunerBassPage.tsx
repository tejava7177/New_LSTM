// src/pages/TunerBassPage.tsx
import { useState } from 'react'
import DeviceSelect from '../components/DeviceSelect'
import { usePitch } from '../hooks/usePitch'
import { noteFromFreq, centsOff } from '../utils/noteUtils'
import Gauge from '../components/Gauge'       // 기존 게이지 재사용

export default function TunerBassPage() {
  const [deviceId, setDeviceId] = useState<string>()
  // 베이스: FFT 8192, 감도 살짝 올려 잡음 억제
  const pitch = usePitch(deviceId, { fftSize: 8192, minVolumeRms: 0.02 })
  const note = pitch ? noteFromFreq(pitch) : null
  const cents = pitch && note ? centsOff(pitch, note.freq) : 0

  return (
    <div style={{ padding: 16 }}>
      <h2>🎸 베이스 튜너</h2>
      <DeviceSelect value={deviceId || ''} onChange={setDeviceId} />

      {pitch ? (
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Gauge cents={cents} />
          <div style={{ fontSize: 64, fontWeight: 700 }}>{note.name}</div>
          <div>{pitch.toFixed(1)} Hz / {cents>0 ? '+' : ''}{cents.toFixed(0)} cents</div>
        </div>
      ) : (
        <p style={{ marginTop: 24 }}>입력 신호를 감지 중…</p>
      )}
    </div>
  )
}