// src/hooks/usePitch.ts
import { useEffect, useRef, useState } from 'react'

/**
 * 실시간 피치 추정 훅
 *
 * @param deviceId   getUserMedia deviceId (미지정 시 기본 입력)
 * @param opts.fftSize      분석 FFT 사이즈(기본 2048 / 베이스 8192 권장)
 * @param opts.minVolumeRms 최소 RMS(볼륨) – 배경 잡음 컷오프
 */
export function usePitch(
  deviceId?: string,
  opts: { fftSize?: number; minVolumeRms?: number } = {}
) {
  const { fftSize = 2048, minVolumeRms = 0.01 } = opts

  const [pitch, setPitch] = useState<number | null>(null)
  const analyserRef = useRef<AnalyserNode>()
  const rafRef = useRef<number>()

  useEffect(() => {
    let audioCtx: AudioContext
    let source: MediaStreamAudioSourceNode

    async function init() {
      audioCtx = new AudioContext()
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true
      })
      source = audioCtx.createMediaStreamSource(stream)

      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = fftSize          // ← 사용자 지정 해상도
      analyserRef.current = analyser

      source.connect(analyser)
      tick()
    }
    init().catch(console.error)

    function tick() {
      const analyser = analyserRef.current
      if (!analyser) return

      const buf = new Float32Array(analyser.fftSize)
      analyser.getFloatTimeDomainData(buf)

      const f = autoCorrelate(buf, analyser.context.sampleRate, minVolumeRms)
      setPitch(f)

      rafRef.current = requestAnimationFrame(tick)
    }

    /** 정리 */
    return () => {
      cancelAnimationFrame(rafRef.current!)
      source?.disconnect()
      audioCtx?.close()
    }
  }, [deviceId, fftSize, minVolumeRms])

  return pitch
}

/* ───── 오토코릴레이션 기반 피치 추정 ───── */
function autoCorrelate(
  buf: Float32Array,
  sampleRate: number,
  minRms: number
): number | null {
  const SIZE = buf.length
  const MAX_SAMPLES = Math.floor(SIZE / 2)
  let bestOffset = -1
  let bestCorrelation = 0
  let rms = 0

  for (let i = 0; i < SIZE; i++) rms += buf[i] * buf[i]
  rms = Math.sqrt(rms / SIZE)
  if (rms < minRms) return null  // 입력 레벨이 너무 작으면 무시

  let lastCorrelation = 1
  for (let offset = 0; offset < MAX_SAMPLES; offset++) {
    let correlation = 0
    for (let i = 0; i < MAX_SAMPLES; i++)
      correlation += Math.abs(buf[i] - buf[i + offset])
    correlation = 1 - correlation / MAX_SAMPLES

    if (correlation > 0.9 && correlation > lastCorrelation) {
      bestCorrelation = correlation
      bestOffset = offset
    } else if (bestCorrelation > 0.9 && correlation < lastCorrelation) {
      // 피크 지점 통과 → 주파수 계산
      return sampleRate / bestOffset
    }
    lastCorrelation = correlation
  }
  return null
}