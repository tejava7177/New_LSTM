// frontend/src/components/ScrollRecordWave.tsx
import React, { useEffect, useRef } from 'react';

type Props = {
  mediaStream?: MediaStream | null;   // useMediaRecorder에서 받은 recordStream
  running: boolean;                   // 녹음 중이면 true
  theme?: 'light' | 'dark';
  height?: number;
  seconds?: number;                   // 화면에 보이는 최근 히스토리 길이(초)
  pxPerSec?: number;                  // 초당 몇 px로 스크롤할지
  clearOnStart?: boolean;             // 녹음 시작 시 히스토리 초기화
};

export default function ScrollRecordWave({
  mediaStream,
  running,
  theme = 'light',
  height = 120,
  seconds = 80,
  pxPerSec = 80,
  clearOnStart = true,
}: Props) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const cvRef = useRef<HTMLCanvasElement | null>(null);

  const acRef = useRef<AudioContext | null>(null);
  const srcRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const anRef  = useRef<AnalyserNode | null>(null);

  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number | null>(null);

  // 히스토리(시간축으로 누적). 값: -1..+1
  const historyRef = useRef<number[]>([]);

  // DPI 세팅
  function sizeCanvas() {
    const cv = cvRef.current, wrap = wrapRef.current;
    if (!cv || !wrap) return;
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const W = wrap.clientWidth * dpr;
    const H = height * dpr;
    if (cv.width !== Math.floor(W) || cv.height !== Math.floor(H)) {
      cv.width = Math.floor(W);
      cv.height = Math.floor(H);
      cv.style.width = '100%';
      cv.style.height = `${height}px`;
    }
  }

  // 그리기(최근 width픽셀만 사용)
  function draw() {
    const cv = cvRef.current; if (!cv) return;
    const g = cv.getContext('2d'); if (!g) return;

    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const W = cv.width, H = cv.height, mid = Math.floor(H / 2);
    const bg = theme === 'light' ? '#ffffff' : '#0b1220';
    const grid = theme === 'light' ? '#e5e7eb' : '#1f2937';
    const stroke = theme === 'light' ? '#3b82f6' : '#60a5fa';
    const fill = theme === 'light' ? '#93c5fd' : '#a78bfa';

    g.clearRect(0,0,W,H);
    g.fillStyle = bg; g.fillRect(0,0,W,H);

    // 중앙선
    g.strokeStyle = grid; g.lineWidth = 1 * dpr;
    g.beginPath(); g.moveTo(0, mid + 0.5 * dpr); g.lineTo(W, mid + 0.5 * dpr); g.stroke();

    // 히스토리 → 화면폭에 맞춰 마지막 W 픽셀만 사용
    const hist = historyRef.current;
    const needed = W; // 픽셀당 1포인트
    const start = Math.max(0, hist.length - needed);
    const view = hist.slice(start);

    // 파형(선 + 채움)
    const scale = H * 0.45; // 진폭 스케일
    if (view.length > 1) {
      g.beginPath();
      for (let x = 0; x < view.length; x++) {
        const y = mid + view[x] * scale;
        if (x === 0) g.moveTo(x, y);
        else g.lineTo(x, y);
      }
      g.strokeStyle = stroke; g.lineWidth = 2 * dpr; g.stroke();

      // 채움(아래쪽 닫아주기)
      g.lineTo(view.length - 1, mid); g.lineTo(0, mid); g.closePath();
      g.globalAlpha = 0.25; g.fillStyle = fill; g.fill(); g.globalAlpha = 1;
    }
  }

  // 오디오 + 수집 루프
  function loop(ts: number) {
    const an = anRef.current; const cv = cvRef.current;
    if (!an || !cv) return;

    if (lastTsRef.current == null) lastTsRef.current = ts;
    const dt = (ts - lastTsRef.current) / 1000;
    lastTsRef.current = ts;

    const appendCols = Math.max(1, Math.round(dt * pxPerSec)); // 이번 프레임에서 추가할 지점 수
    const buf = new Float32Array(an.fftSize);
    an.getFloatTimeDomainData(buf);

    // buf에서 균일 간격으로 샘플을 뽑아 appendCols개 추가
    for (let i = 0; i < appendCols; i++) {
      const idx = Math.floor((i + 1) / (appendCols + 1) * (buf.length - 1));
      historyRef.current.push(buf[idx]);
    }

    // seconds * pxPerSec 만큼만 유지
    const maxPoints = Math.floor(seconds * pxPerSec);
    if (historyRef.current.length > maxPoints) {
      historyRef.current.splice(0, historyRef.current.length - maxPoints);
    }

    draw();
    rafRef.current = requestAnimationFrame(loop);
  }

  // running 변화 시 오디오 연결/해제 + clearOnStart 처리
  useEffect(() => {
    sizeCanvas();
    if (!mediaStream || !running) {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      if (acRef.current && acRef.current.state !== 'closed') { acRef.current.close().catch(()=>{}); }
      acRef.current = null; srcRef.current = null; anRef.current = null;
      // 멈춰도 화면은 유지(기록된 파형을 남김)
      return;
    }

    if (clearOnStart) historyRef.current = [];

    const AC: any = (window as any).AudioContext || (window as any).webkitAudioContext;
    const ac = new AC(); acRef.current = ac;
    const src = ac.createMediaStreamSource(mediaStream); srcRef.current = src;
    const an = ac.createAnalyser(); anRef.current = an;
    an.fftSize = 1024; an.smoothingTimeConstant = 0;

    src.connect(an);
    lastTsRef.current = null;
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      try { src.disconnect(); } catch {}
      if (ac && ac.state !== 'closed') ac.close().catch(()=>{});
      acRef.current = null; srcRef.current = null; anRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mediaStream, running, seconds, pxPerSec, theme]);

  // 리사이즈 대응
  useEffect(() => {
    const onR = () => { sizeCanvas(); draw(); };
    window.addEventListener('resize', onR);
    onR();
    return () => window.removeEventListener('resize', onR);
  }, [theme, height]);

  return (
    <div ref={wrapRef} style={{
      width: '100%',
      border: theme === 'light' ? '1px solid #e5e7eb' : '1px solid #1f2937',
      borderRadius: 8, padding: 8,
      background: theme === 'light' ? '#fff' : '#0b1220'
    }}>
      <canvas ref={cvRef} />
      <div style={{fontSize:12, color: theme==='light' ? '#6b7280' : '#9ca3af', marginTop:4}}>
        파형-스크롤(최근 {seconds}s 기록) • {pxPerSec}px/s
      </div>
    </div>
  );
}