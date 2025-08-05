export async function uploadBlob(blob: Blob) {
  const form = new FormData();
  form.append('audio', blob, 'recording.webm');
  const res = await fetch('/api/audio/upload', { method: 'POST', body: form });
  if (!res.ok) throw new Error('upload failed');
  return res.json() as Promise<{ id: string; url: string }>;
}
