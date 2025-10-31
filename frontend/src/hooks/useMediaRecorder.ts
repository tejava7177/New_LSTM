import { useEffect, useRef, useState } from 'react'

type UseMediaRecorderReturn = {
  recording: boolean
  blobUrl?: string
  error?: string
  start: () => Promise<void>
  stop: () => void
}

type UseMediaRecorderOpts = {
  inputStream?: MediaStream       // AMP 출력 전달 시 사용
  mimeHint?: string               // 예: 'audio/webm;codecs=opus'
  channelMode?: 'dual-mono' | 'passthrough' // 마이크 직접 녹음 시
}

function pickMimeType(hint?: string): string | undefined {
  const MR: any = (window as any).MediaRecorder
  if (!MR || typeof MR.isTypeSupported !== 'function') return hint
  const candidates = [hint,'audio/webm;codecs=opus','audio/webm','audio/mp4;codecs=mp4a.40.2','audio/mp4','audio/ogg;codecs=opus','audio/ogg']
    .filter(Boolean) as string[]
  return candidates.find((t) => MR.isTypeSupported(t))
}

export function useMediaRecorder(
  deviceId?: string,
  opts?: UseMediaRecorderOpts
): UseMediaRecorderReturn {
  const [recording, setRecording] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string>()
  const [error, setError] = useState<string>()

  const mediaStreamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  const acRef = useRef<AudioContext | null>(null)
  const destRef = useRef<MediaStreamAudioDestinationNode | null>(null)
  const usingExternalRef = useRef(false)

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
      try { recorderRef.current?.stop() } catch {}
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
    }
  }, [blobUrl])

  async function start() {
    try {
      setError(undefined)
      if (blobUrl) { URL.revokeObjectURL(blobUrl); setBlobUrl(undefined) }

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

      let recordStream: MediaStream
      if (usingExternalRef.current) {
        recordStream = inStream
      } else {
        const AC: any = (window as any).AudioContext || (window as any).webkitAudioContext
        const ac: AudioContext = new AC()
        acRef.current = ac

        const src = ac.createMediaStreamSource(inStream)
        const dest = ac.createMediaStreamDestination()
        destRef.current = dest

        if ((opts?.channelMode ?? 'dual-mono') === 'dual-mono') {
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
    }
  }

  function stop() {
    try {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop()
      if (!usingExternalRef.current) mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
      if (acRef.current && acRef.current.state !== 'closed') acRef.current.close().catch(() => {})
    } finally {
      setRecording(false)
    }
  }

  return { recording, blobUrl, error, start, stop }
}