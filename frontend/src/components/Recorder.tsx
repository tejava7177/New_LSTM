// src/components/Recorder.tsx
import { useEffect, useState } from 'react'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { uploadBlob } from '../lib/api'

/**
 * 녹음/미리듣기/업로드 컴포넌트
 * - deviceId: 선택한 입력 장치(deviceId) (옵션)
 */
export default function Recorder({ deviceId }: { deviceId?: string }) {
  const { recording, blobUrl, start, stop } = useMediaRecorder(deviceId)
  const [serverUrl, setServerUrl] = useState<string>()

  /** 업로드 */
  async function upload() {
    if (!blobUrl) return
    const blob = await fetch(blobUrl).then(r => r.blob())
    const { url } = await uploadBlob(blob)
    setServerUrl(url)
  }

  // 장치가 바뀌면 업로드 URL 초기화
  useEffect(() => setServerUrl(undefined), [deviceId])

  return (
    <div>
      {/* 녹음/정지 버튼 */}
      {!recording ? (
        <button onClick={start}>녹음 시작</button>
      ) : (
        <button onClick={stop}>정지</button>
      )}

      {/* 녹음 중 표시 */}
      {recording && (
        <div style={{ marginTop: 6, fontWeight: 500 }}>
          <span className="rec-indicator" />녹음 중…
        </div>
      )}

      {/* 미리듣기 영역 */}
      <div style={{ marginTop: 8 }}>
        <strong>미리듣기</strong>
        {blobUrl ? (
          <audio src={blobUrl} controls />
        ) : (
          <div>녹음 후 미리듣기 가능</div>
        )}
      </div>

      {/* 업로드 버튼/결과 */}
      <div style={{ marginTop: 8 }}>
        <button onClick={upload} disabled={!blobUrl}>
          서버 업로드
        </button>
        {serverUrl && (
          <div style={{ marginTop: 6 }}>
            업로드됨:{' '}
            <a href={serverUrl} target="_blank" rel="noreferrer">
              {serverUrl}
            </a>
          </div>
        )}
      </div>
    </div>
  )
}