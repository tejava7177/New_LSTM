// src/components/DeviceSelect.tsx
import { useEffect, useState } from 'react'

type Props = {
  value?: string
  onChange?: (v: string) => void
  className?: string
  selectClassName?: string
  /** 내장 버튼 숨김/표시 (기본값: true) */
  showPermissionButton?: boolean
  showRefreshButton?: boolean
}

export default function DeviceSelect({
  value,
  onChange,
  className,
  selectClassName,
  showPermissionButton = false,
  showRefreshButton = false,
}: Props) {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])

  async function refresh() {
    try {
      const all = await navigator.mediaDevices.enumerateDevices()
      setDevices(all.filter(d => d.kind === 'audioinput'))
    } catch {
      // 권한 없으면 enumerate 실패할 수 있음
    }
  }

  async function askPermission() {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true })
      s.getTracks().forEach(t => t.stop())
      await refresh()
    } catch {
      // 사용자가 거부한 경우 등
    }
  }

  useEffect(() => {
    // 권한이 이미 허용되어 있으면 바로 목록 로드
    const anyNav: any = navigator
    if (anyNav?.permissions?.query) {
      anyNav.permissions
        .query({ name: 'microphone' })
        .then((p: any) => {
          if (p.state === 'granted') refresh()
          // 상태 변화 감지 시 갱신
          if (p.addEventListener) {
            p.addEventListener('change', () => {
              if (p.state === 'granted') refresh()
            })
          }
        })
        .catch(refresh)
    } else {
      // Safari 등 Permissions API 미지원 브라우저
      refresh()
    }
  }, [])

  // 라벨이 비어있는 장치 대응
  const labelFor = (d: MediaDeviceInfo, idx: number) =>
    d.label && d.label.trim().length > 0 ? d.label : `입력 장치 ${idx + 1}`

  return (
    <div className={className}>
      {showPermissionButton && (
        <button className="ds-perm" onClick={askPermission}>
          마이크 권한
        </button>
      )}

      <select
        className={selectClassName}
        value={value ?? ''}
        onChange={e => onChange?.(e.target.value)}
        style={{ marginLeft: showPermissionButton ? 8 : 0 }}
        aria-label="오디오 입력 장치 선택"
      >
        <option value="">기본 장치</option>
        {devices.map((d, i) => (
          <option key={d.deviceId || i} value={d.deviceId}>
            {labelFor(d, i)}
          </option>
        ))}
      </select>

      {showRefreshButton && (
        <button className="ds-refresh" onClick={refresh} style={{ marginLeft: 8 }}>
          새로고침
        </button>
      )}
    </div>
  )
}