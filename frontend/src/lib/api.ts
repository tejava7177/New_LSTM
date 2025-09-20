export async function uploadBlob(blob: Blob) {
  const form = new FormData();
  form.append('audio', blob, 'recording.webm');
  const res = await fetch('/api/audio/upload', { method: 'POST', body: form });
  if (!res.ok) throw new Error('upload failed');
  return res.json() as Promise<{ id: string; url: string }>;
}

export async function fetchList() {
  return fetch('/api/audio/list').then(r => r.json()) as
         Promise<{id: string; size: number; created: string}[]>;
}
export async function deleteFile(id: string) {
  return fetch('/api/audio/' + id, { method: 'DELETE' });
}

export async function midiToWav(file: File) {
  const fd = new FormData();
  fd.append('midi', file, file.name);
  const res = await fetch('/api/render/midi-to-wav', { method: 'POST', body: fd });
  if (!res.ok) throw new Error('MIDI 렌더 실패');
  return res.json() as Promise<{ id: string; url: string; duration: number }>;
}