// src/lib/mixdown.ts
export async function mixBuffersToAudioBuffer(
  midiBuf: AudioBuffer,
  bassBuf: AudioBuffer,
  { sampleRate = 48000, fadeOutSec = 0.02 } = {}
): Promise<AudioBuffer> {
  const dur = Math.max(midiBuf.duration, bassBuf.duration)
  const length = Math.ceil(dur * sampleRate)

  const ctx = new OfflineAudioContext(2, length, sampleRate)

  // MIDI
  const s1 = ctx.createBufferSource()
  s1.buffer = midiBuf
  const g1 = ctx.createGain()
  g1.gain.value = 0.9
  s1.connect(g1).connect(ctx.destination)
  s1.start(0)

  // Bass
  const s2 = ctx.createBufferSource()
  s2.buffer = bassBuf
  const g2 = ctx.createGain()
  g2.gain.value = 1.0
  s2.connect(g2).connect(ctx.destination)
  s2.start(0)

  // 아주 짧게 페이드아웃(클릭 방지)
  const tEnd = length / sampleRate
  g1.gain.setValueAtTime(g1.gain.value, tEnd - fadeOutSec)
  g1.gain.linearRampToValueAtTime(0, tEnd)
  g2.gain.setValueAtTime(g2.gain.value, tEnd - fadeOutSec)
  g2.gain.linearRampToValueAtTime(0, tEnd)

  return ctx.startRendering()
}