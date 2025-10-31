import { useEffect, useRef, useState } from 'react'

type UseMediaRecorderReturn = {
  recording: boolean
  blobUrl?: string
  error?: string
  start: () => Promise<void>
  stop: () => void
  /** 실녹음에 쓰이는 MediaStream (파형-스크롤용) */
  recordStream: MediaStream | null
}

type UseMediaRecorderOpts = {
  /** AMP 등 외부에서 가공된 스트림을 그대로 녹음 */
  inputStream?: MediaStream
  /** mimeType 힌트 (브라우저 미지원 시 자동 폴백) */
  mimeHint?: string
  /** 마이크 직접 녹음 시 채널 처리 모드 */
  channelMode?: 'dual-mono' | 'passthrough'
}

/** 지원되는 mimeType 선택 */
function pickMimeType(hint?: string): string | undefined {
  const MR: any = (window as any).MediaRecorder
  if (!MR || typeof MR.isTypeSupported !== 'function') return hint
  const candidates = [
    hint,
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4;codecs=mp4a.40.2',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ].filter(Boolean) as string[]
  return candidates.find((t) => MR.isTypeSupported(t))
}

export function useMediaRecorder(
  deviceId?: string,
  opts?: UseMediaRecorderOpts
): UseMediaRecorderReturn {
  const [recording, setRecording] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string>()
  const [error, setError] = useState<string>()

  // 파형 컴포넌트에 전달할 스트림 (state로 노출해 리렌더 트리거)
  const [recordStreamState, setRecordStreamState] = useState<MediaStream | null>(null)

  const mediaStreamRef = useRef<MediaStream | null>(null)              // 입력 원천
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  const acRef = useRef<AudioContext | null>(null)
  const destRef = useRef<MediaStreamAudioDestinationNode | null>(null) // 내부 라우팅 목적지
  const usingExternalRef = useRef(false)

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
      try { recorderRef.current?.stop() } catch {}

      // 외부 스트림은 건드리지 않음
      if (!usingExternalRef.current) {
        mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
      }
      if (acRef.current && acRef.current.state !== 'closed') {
        acRef.current.close().catch(() => {})
      }
      mediaStreamRef.current = null
      recorderRef.current = null
      destRef.current = null
      acRef.current = null
      setRecordStreamState(null)
    }
  }, [blobUrl])

  async function start() {
    try {
      setError(undefined)
      if (blobUrl) { URL.revokeObjectURL(blobUrl); setBlobUrl(undefined) }

      // 1) 입력 스트림 결정
      let inStream: MediaStream
      if (opts?.inputStream) {
        usingExternalRef.current = true
        inStream = opts.inputStream
      } else {
        usingExternalRef.current = false
        const constraints: MediaStreamConstraints = {
          audio: deviceId
            ? { deviceId: { exact: deviceId }, echoCancellation:false, noiseSuppression:false, autoGainControl:false }
            : { echoCancellation:false, noiseSuppression:false, autoGainControl:false },
        }
        inStream = await navigator.mediaDevices.getUserMedia(constraints)
      }
      mediaStreamRef.current = inStream

      // 2) 실제 녹음에 사용할 스트림 구성
      let recordStream: MediaStream
      if (usingExternalRef.current) {
        // 외부(AMP 등) 스트림 그대로
        recordStream = inStream
      } else {
        const AC: any = (window as any).AudioContext || (window as any).webkitAudioContext
        const ac: AudioContext = new AC()
        acRef.current = ac

        const src = ac.createMediaStreamSource(inStream)
        const dest = ac.createMediaStreamDestination()
        destRef.current = dest

        if ((opts?.channelMode ?? 'dual-mono') === 'dual-mono') {
          // L(0) 복제 → L/R
          const splitter = ac.createChannelSplitter(2)
          const merger = ac.createChannelMerger(2)
          src.connect(splitter)
          splitter.connect(merger, 0, 0)
          splitter.connect(merger, 0, 1)
          merger.connect(dest)
        } else {
          src.connect(dest)
        }

        try { if (ac.state === 'suspended') await ac.resume() } catch {}
        recordStream = dest.stream
      }

      // 파형용으로 노출
      setRecordStreamState(recordStream)

      // 3) MediaRecorder
      const mime = pickMimeType(opts?.mimeHint)
      const rec = new (window as any).MediaRecorder(recordStream, mime ? { mimeType: mime } : undefined)
      recorderRef.current = rec
      chunksRef.current = []

      rec.ondataavailable = (e: any) => { if (e.data && e.data.size) chunksRef.current.push(e.data) }
      rec.onstop = () => {
        try {
          const type = rec.mimeType || mime || 'audio/webm'
          const blob = new Blob(chunksRef.current, { type })
          const url = URL.createObjectURL(blob)
          setBlobUrl(url)
        } catch (err: any) {
          setError(err?.message ?? String(err))
        }
      }

      rec.start()
      setRecording(true)
    } catch (err: any) {
      setError(err?.message ?? String(err))
      setRecording(false)
      setRecordStreamState(null)
    }
  }

  function stop() {
    try {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop()
      }
      // 외부 스트림은 정지하지 않음
      if (!usingExternalRef.current) {
        mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
      }
      if (acRef.current && acRef.current.state !== 'closed') {
        acRef.current.close().catch(() => {})
      }
    } finally {
      setRecording(false)
      // 파형 즉시 정지되도록 노출 스트림만 끊어줌(외부 스트림 자체는 유지)
      setRecordStreamState(null)
    }
  }

  return {
  recording, blobUrl, error, start, stop,
  recordStream: usingExternalRef.current
    ? mediaStreamRef.current
    : (destRef.current?.stream ?? null),
};
}