// src/hooks/usePitch.ts
import { useEffect, useRef, useState } from 'react'
import Pitchfinder from 'pitchfinder'

type Opts = {
  fftSize?: number
  minVolumeRms?: number
  lpfHz?: number        // 저역만 남기기 위한 저역통과 상한 (베이스 300~400)
  hpfHz?: number        // 초저역/DC 제거 (20~30)
  preferFundamental?: boolean // 고조파로 튀면 1/2, 1/3 후보 비교
}

export function usePitch(
  deviceId?: string,
  {
    fftSize = 8192,
    minVolumeRms = 0.02,
    lpfHz = 350,
    hpfHz = 25,
    preferFundamental = true,
  }: Opts = {}
) {
  const [pitch, setPitch] = useState<number | null>(null)
  const analyserRef = useRef<AnalyserNode>()
  const rafRef = useRef<number>()

  useEffect(() => {
    let audioCtx: AudioContext
    let source: MediaStreamAudioSourceNode
    let hpf: BiquadFilterNode
    let lpf: BiquadFilterNode

    async function init() {
      audioCtx = new AudioContext()
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      })

      source = audioCtx.createMediaStreamSource(stream)

      // ── 전처리 필터 체인: HPF → LPF → Analyser
      hpf = audioCtx.createBiquadFilter()
      hpf.type = 'highpass'
      hpf.frequency.value = hpfHz

      lpf = audioCtx.createBiquadFilter()
      lpf.type = 'lowpass'
      lpf.frequency.value = lpfHz

      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = fftSize

      source.connect(hpf)
      hpf.connect(lpf)
      lpf.connect(analyser)

      analyserRef.current = analyser
      tick()
    }
    init().catch(console.error)

    // YIN 디텍터(피치파인더)
    // threshold(무주기성 임계)를 살짝 낮추면 저음에서 락이 쉬워짐
    let detector: (buf: Float32Array) => number | null
    const setDetector = (sampleRate: number) => {
      detector = Pitchfinder.YIN({ sampleRate, threshold: 0.1 })
    }

    function tick() {
      const analyser = analyserRef.current
      if (!analyser) return

      const ctx = analyser.context as AudioContext
      if (!detector) setDetector(ctx.sampleRate)

      const buf = new Float32Array(analyser.fftSize)
      analyser.getFloatTimeDomainData(buf)

      // 입력 레벨 체크
      let rms = 0
      for (let i = 0; i < buf.length; i++) rms += buf[i] * buf[i]
      rms = Math.sqrt(rms / buf.length)
      if (rms < minVolumeRms) {
        setPitch(null)
      } else {
        let f = detector(buf) // YIN 주파수 (null 가능)
        if (f && preferFundamental) {
          // 서브하모닉 후보와 비교해 더 안정적인(낮은) 주파수 선택
          const candidates = [f, f / 2, f / 3].filter(x => x >= 30)
          f = chooseBestFundamental(candidates)
        }
        setPitch(f ?? null)
      }

      rafRef.current = requestAnimationFrame(tick)
    }

    return () => {
      cancelAnimationFrame(rafRef.current!)
      try {
        lpf?.disconnect()
        hpf?.disconnect()
        source?.disconnect()
        audioCtx?.close()
      } catch {}
    }
  }, [deviceId, fftSize, minVolumeRms, lpfHz, hpfHz, preferFundamental])

  return pitch
}

/** 후보들 중 ‘가장 음정 오차가 작은 주파수’를 선택(근본음 선호) */
function chooseBestFundamental(cands: number[]) {
  const { noteFromFreq, centsOff } = noteMath
  let best = cands[0]
  let bestErr = Math.abs(centsOff(best, noteFromFreq(best).freq))
  for (const f of cands.slice(1)) {
    const err = Math.abs(centsOff(f, noteFromFreq(f).freq))
    if (err <= bestErr) {
      best = f
      bestErr = err
    }
  }
  return best
}

// 수학 유틸(로컬 경량 버전) – 외부 파일에서 이미 제공한다면 교체 가능
const log2 = (x: number) => Math.log(x) / Math.LN2
const noteMath = {
  noteFromFreq(freq: number) {
    const A4 = 440
    const midi = Math.round(69 + 12 * log2(freq / A4))
    const target = A4 * Math.pow(2, (midi - 69) / 12)
    return { freq: target, midi }
  },
  centsOff(freq: number, target: number) {
    return 1200 * log2(freq / target)
  },
}