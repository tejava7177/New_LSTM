import { useEffect, useRef, useState } from 'react'

export function useMediaRecorder(deviceId?: string) {
  const [recording, setRecording] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string>()
  const mediaStreamRef = useRef<MediaStream|null>(null)
  const recorderRef = useRef<MediaRecorder|null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: deviceId ? { deviceId: { exact: deviceId } } : true
    })
    mediaStreamRef.current = stream
    const mime = ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/ogg']
      .find(m => (window as any).MediaRecorder && MediaRecorder.isTypeSupported(m)) || undefined
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
    recorderRef.current = rec
    chunksRef.current = []
    rec.ondataavailable = e => e.data.size && chunksRef.current.push(e.data)
    rec.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
      setBlobUrl(URL.createObjectURL(blob))
    }
    rec.start()
    setRecording(true)
  }

  function stop() {
    recorderRef.current?.stop()
    mediaStreamRef.current?.getTracks().forEach(t => t.stop())
    setRecording(false)
  }

  return { recording, blobUrl, start, stop }
}
