// src/lib/tracks.ts
export type TrackOptions = {
  /** 생성된 진행을 몇 번 반복할지 (기본 6회) */
  repeats?: number;
  // 필요한 옵션을 자유롭게 확장
  [key: string]: any;
};

export type GeneratePayload = {
  genre: string;
  progression: string[];
  tempo: number;
  options?: TrackOptions; // ← 타입을 구체화
};

export type JobResponse = { jobId: string };
export type StatusResponse = { status: 'PENDING'|'RUNNING'|'DONE'|'ERROR'; progress: number };

export async function generateTrack(body: GeneratePayload): Promise<JobResponse> {
  const res = await fetch('/api/tracks/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`generate failed: ${res.status}`);
  return res.json();
}

export async function getTrackStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`/api/tracks/status/${jobId}`);
  if (!res.ok) throw new Error(`status failed: ${res.status}`);
  return res.json();
}

export const midiUrl = (jobId: string) => `/api/tracks/${jobId}/midi`;
export const xmlUrl  = (jobId: string) => `/api/tracks/${jobId}/musicxml`;

// ★ 추가: WAV 엔드포인트
export const wavUrl  = (jobId: string) => `/api/tracks/${jobId}/wav`;

// (선택) 바로 Blob 가져오는 헬퍼
export async function fetchTrackWav(jobId: string): Promise<Blob> {
  const res = await fetch(wavUrl(jobId));
  if (!res.ok) throw new Error(`wav download failed: ${res.status}`);
  return res.blob();
}