import { useEffect, useState } from 'react'

type Props = { value: string; onChange: (v: string) => void }

export default function DeviceSelect({ value, onChange }: Props) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])

  async function askPermission() {
    const s = await navigator.mediaDevices.getUserMedia({ audio: true })
    s.getTracks().forEach(t => t.stop())
    await refresh()
  }

  async function refresh() {
    const all = await navigator.mediaDevices.enumerateDevices()
    setDevices(all.filter(d => d.kind === 'audioinput'))
  }

  useEffect(() => {
    ;(navigator as any).permissions?.query({ name: 'microphone' })
      .then((p: any) => p.state === 'granted' && refresh())
      .catch(() => {})
  }, [])

  return (
    <div>
      <button onClick={askPermission}>마이크 권한</button>
      <select value={value} onChange={e => onChange(e.target.value)} style={{marginLeft:8}}>
        <option value=''>기본 장치</option>
        {devices.map(d => (
          <option key={d.deviceId} value={d.deviceId}>{d.label || d.deviceId}</option>
        ))}
      </select>
      <button onClick={refresh} style={{marginLeft:8}}>새로고침</button>
    </div>
  )
}
