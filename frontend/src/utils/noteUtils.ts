
//const log2 = (x: number) => Math.log(x) / Math.LN2
// 12-TET 기준
export function noteFromFreq(freq: number) {
  const A4 = 440
  const SEMI = 1200 * Math.log2(freq / A4)
  const noteNum = Math.round(SEMI / 100) + 57 // 0=C0 … 69=A4; 69-12=57
  const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  const name = names[(noteNum + 1200) % 12] // wrap
  const targetFreq = A4 * 2 ** ((noteNum - 69) / 12)
  return { name, freq: targetFreq }
}

export function centsOff(freq: number, target: number) {
  return 1200 * Math.log2(freq / target)
}