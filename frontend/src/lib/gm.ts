// 최소 사용 악기만 매핑(필요하면 계속 추가)
export const GM_NAME: Record<number, string> = {
  0:  'acoustic_grand_piano',
  24: 'acoustic_guitar_nylon',
  25: 'acoustic_guitar_steel',
  29: 'overdriven_guitar',
  30: 'distortion_guitar',
  32: 'acoustic_bass',
  33: 'electric_bass_finger',
  34: 'electric_bass_pick',
  48: 'string_ensemble_1',
  56: 'trumpet',
  73: 'flute',
};

export function programToSfName(p: number) {
  return GM_NAME[p] ?? 'acoustic_grand_piano';
}