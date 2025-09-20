import { useEffect, useRef, useState } from 'react'

type UseMediaRecorderReturn = {
  recording: boolean
  blobUrl?: string
  error?: string
  start: () => Promise<void>
  stop: () => void
}

/** 브라우저에서 지원되는 오디오 mimeType을 고른다(사파리 포함). */
function pickMimeType(): string | undefined {
  const MR: any = (window as any).MediaRecorder
  if (!MR || typeof MR.isTypeSupported !== 'function') return undefined
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4;codecs=mp4a.40.2', // Safari 계열
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ]
  return candidates.find((t) => MR.isTypeSupported(t))
}

export function useMediaRecorder(deviceId?: string): UseMediaRecorderReturn {
  const [recording, setRecording] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string>()
  const [error, setError] = useState<string>()

  const mediaStreamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  // 언마운트/새 녹음 시작 시 URL 정리
  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
      recorderRef.current?.stop()
    }
  }, [blobUrl])

  async function start() {
    try {
      setError(undefined)
      // 기존 URL/상태 정리
      if (blobUrl) URL.revokeObjectURL(blobUrl)
      setBlobUrl(undefined)

      const constraints: MediaStreamConstraints = {
        audio: deviceId
          ? { deviceId: { exact: deviceId }, echoCancellation: false, noiseSuppression: false }
          : { echoCancellation: false, noiseSuppression: false },
      }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      mediaStreamRef.current = stream

      const mime = pickMimeType()
      const rec = new (window as any).MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      recorderRef.current = rec
      chunksRef.current = []

      rec.ondataavailable = (e: BlobEvent) => {
        if (e.data && e.data.size) chunksRef.current.push(e.data)
      }
      rec.onstop = () => {
        try {
          const type = rec.mimeType || mime || 'audio/webm'
          const blob = new Blob(chunksRef.current, { type })
          const url = URL.createObjectURL(blob)
          setBlobUrl(url)
        } catch (e: any) {
          setError(e?.message ?? String(e))
        }
      }

      rec.start() // timeslice 없이 stop 시점에 합쳐서 받음
      setRecording(true)
    } catch (e: any) {
      setError(e?.message ?? String(e))
      setRecording(false)
    }
  }

  function stop() {
    try {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop()
      }
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    } finally {
      setRecording(false)
    }
  }

  return { recording, blobUrl, error, start, stop }
}