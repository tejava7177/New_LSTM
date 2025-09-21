import { useEffect, useRef, useState } from 'react'

type UseMediaRecorderReturn = {
  recording: boolean
  blobUrl?: string
  error?: string
  start: () => Promise<void>
  stop: () => void
}

/** 브라우저별 지원 mimeType 중 가능한 것을 선택 */
function pickMimeType(): string | undefined {
  const MR: any = (window as any).MediaRecorder
  if (!MR || typeof MR.isTypeSupported !== 'function') return undefined
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4;codecs=mp4a.40.2', // Safari
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ]
  return candidates.find((t) => MR.isTypeSupported(t))
}

/**
 * 마이크/오디오 인터페이스 입력을 받아
 * - L 채널(또는 단일 채널)을 L/R로 복제(듀얼 모노)하여
 * - MediaRecorder 로 녹음합니다.
 */
export function useMediaRecorder(deviceId?: string): UseMediaRecorderReturn {
  const [recording, setRecording] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string>()
  const [error, setError] = useState<string>()

  const mediaStreamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  // WebAudio 라우팅(듀얼 모노)용
  const acRef = useRef<AudioContext | null>(null)
  const destRef = useRef<MediaStreamAudioDestinationNode | null>(null)

  // 정리
  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
      try { recorderRef.current?.stop() } catch {}
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
      if (acRef.current && acRef.current.state !== 'closed') acRef.current.close().catch(()=>{})
    }
  }, [blobUrl])

  async function start() {
    try {
      setError(undefined)
      if (blobUrl) { URL.revokeObjectURL(blobUrl); setBlobUrl(undefined) }

      // 1) 입력 스트림 가져오기
      const constraints: MediaStreamConstraints = {
        audio: deviceId
          ? { deviceId: { exact: deviceId }, echoCancellation: false, noiseSuppression: false }
          : { echoCancellation: false, noiseSuppression: false },
      }
      const inStream = await navigator.mediaDevices.getUserMedia(constraints)
      mediaStreamRef.current = inStream

      // 2) WebAudio로 듀얼 모노 라우팅
      const ac = new (window.AudioContext || (window as any).webkitAudioContext)()
      acRef.current = ac

      const src = ac.createMediaStreamSource(inStream)
      // 입력이 1ch/2ch 어떤 형태든 L(0)만을 두 채널로 복제
      const splitter = ac.createChannelSplitter(2)
      const merger = ac.createChannelMerger(2)

      src.connect(splitter)
      splitter.connect(merger, 0, 0) // L -> L
      splitter.connect(merger, 0, 1) // L -> R  (완전 모노)

      const dest = ac.createMediaStreamDestination()
      destRef.current = dest
      merger.connect(dest)

      // 3) MediaRecorder 를 듀얼모노 스트림으로
      const mime = pickMimeType()
      const rec = new (window as any).MediaRecorder(dest.stream, mime ? { mimeType: mime } : undefined)
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

      rec.start() // stop 시점에 합쳐서 수신
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
      if (acRef.current && acRef.current.state !== 'closed') {
        acRef.current.close().catch(()=>{})
      }
    } finally {
      setRecording(false)
    }
  }

  return { recording, blobUrl, error, start, stop }
}