// frontend/src/utils/audioTrim.ts
export async function trimPreRollFromBlobUrl(blobUrl: string, preRollSec: number) {
  const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
  const arr = await (await fetch(blobUrl)).arrayBuffer()
  const src = await ctx.decodeAudioData(arr.slice(0))
  const startSample = Math.floor(preRollSec * src.sampleRate)
  const out = ctx.createBuffer(src.numberOfChannels, Math.max(0, src.length - startSample), src.sampleRate)
  for (let ch = 0; ch < src.numberOfChannels; ch++) {
    out.getChannelData(ch).set(src.getChannelData(ch).subarray(startSample))
  }
  await ctx.close()
  const wav = audioBufferToWav(out)
  const url = URL.createObjectURL(wav)
  return { url, buffer: out }
}

// 아주 가벼운 WAV 인코더(모노/스테레오 대응)
function audioBufferToWav(abuffer: AudioBuffer) {
  const numOfChan = abuffer.numberOfChannels
  const sampleRate = abuffer.sampleRate
  const format = 1
  const bitDepth = 16

  let length = abuffer.length * numOfChan * 2 + 44
  let buffer = new ArrayBuffer(length)
  let view = new DataView(buffer)

  function writeString(view: DataView, offset: number, string: string) {
    for (let i = 0; i < string.length; i++) view.setUint8(offset + i, string.charCodeAt(i))
  }

  let pos = 0
  writeString(view, pos, 'RIFF'); pos += 4
  view.setUint32(pos, length - 8, true); pos += 4
  writeString(view, pos, 'WAVE'); pos += 4
  writeString(view, pos, 'fmt '); pos += 4
  view.setUint32(pos, 16, true); pos += 4
  view.setUint16(pos, format, true); pos += 2
  view.setUint16(pos, numOfChan, true); pos += 2
  view.setUint32(pos, sampleRate, true); pos += 4
  view.setUint32(pos, sampleRate * numOfChan * 2, true); pos += 4
  view.setUint16(pos, numOfChan * 2, true); pos += 2
  view.setUint16(pos, bitDepth, true); pos += 2
  writeString(view, pos, 'data'); pos += 4
  view.setUint32(pos, abuffer.length * numOfChan * 2, true); pos += 4

  // interleave
  let offset = 0
  for (let i = 0; i < abuffer.length; i++) {
    for (let ch = 0; ch < numOfChan; ch++) {
      let sample = abuffer.getChannelData(ch)[i]
      sample = Math.max(-1, Math.min(1, sample))
      view.setInt16(pos + offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
      offset += 2
    }
  }
  return new Blob([view], { type: 'audio/wav' })
}