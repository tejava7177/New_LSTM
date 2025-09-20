// src/lib/wav.ts
export function audioBufferToWavBlob(buffer: AudioBuffer): Blob {
  const numChannels = buffer.numberOfChannels
  const sampleRate = buffer.sampleRate            // ★ 핵심: 버퍼의 실제 샘플레이트 사용
  const format = 1                                // PCM
  const bitDepth = 16

  const samples = buffer.length
  const blockAlign = numChannels * bitDepth / 8
  const byteRate = sampleRate * blockAlign
  const dataSize = samples * blockAlign
  const headerSize = 44
  const totalSize = headerSize + dataSize
  const ab = new ArrayBuffer(totalSize)
  const view = new DataView(ab)

  // ---- WAV 헤더 ----
  writeString(view, 0, "RIFF")
  view.setUint32(4, totalSize - 8, true)
  writeString(view, 8, "WAVE")
  writeString(view, 12, "fmt ")
  view.setUint32(16, 16, true)         // Subchunk1Size
  view.setUint16(20, format, true)     // AudioFormat: PCM=1
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true) // ★ 여기도 buffer.sampleRate
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitDepth, true)
  writeString(view, 36, "data")
  view.setUint32(40, dataSize, true)

  // ---- PCM 데이터(Interleave + Float32 → Int16) ----
  let offset = 44
  const tmp = new Float32Array(samples)
  const channels: Float32Array[] = []
  for (let ch = 0; ch < numChannels; ch++) {
    channels.push(buffer.getChannelData(ch))
  }

  for (let i = 0; i < samples; i++) {
    // 인터리브
    for (let ch = 0; ch < numChannels; ch++) {
      tmp[i] = channels[ch][i]
      // Float32 → Int16
      let s = Math.max(-1, Math.min(1, tmp[i]))
      s = s < 0 ? s * 0x8000 : s * 0x7FFF
      view.setInt16(offset, s, true)
      offset += 2
    }
  }
  return new Blob([view], { type: 'audio/wav' })
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
}