import { useEffect, useState } from 'react'
import { useMediaRecorder } from '../hooks/useMediaRecorder'
import { uploadBlob } from '../lib/api'

export default function Recorder({ deviceId }: { deviceId?: string }) {
  const { recording, blobUrl, start, stop } = useMediaRecorder(deviceId)
  const [serverUrl, setServerUrl] = useState<string>()

  async function upload() {
    if (!blobUrl) return
    const blob = await fetch(blobUrl).then(r => r.blob())
    const { url } = await uploadBlob(blob)
    setServerUrl(url)
  }

  useEffect(() => {
    // 장치 바뀌면 기존 녹음 URL 초기화
    setServerUrl(undefined)
  }, [deviceId])

  return (
    <div>
      {!recording ? (
        <button onClick={start}>녹음 시작</button>
      ) : (
        <button onClick={stop}>정지</button>
      )}
      <div style={{marginTop:8}}>
        <strong>미리듣기</strong>
        {blobUrl ? <audio src={blobUrl} controls /> : <div>녹음 후 미리듣기 가능</div>}
      </div>
      <div style={{marginTop:8}}>
        <button onClick={upload} disabled={!blobUrl}>서버 업로드</button>
        {serverUrl && (
          <div style={{marginTop:6}}>
            업로드됨: <a href={serverUrl} target="_blank" rel="noreferrer">{serverUrl}</a>
          </div>
        )}
      </div>
    </div>
  )
}
