// components/RecordingWaveScroll.tsx
import React, { useEffect, useRef, useState } from "react";

type Props = {
  /** 녹음 중일 때 true – true면 그때부터 캔버스 드로잉 시작 */
  active: boolean;
  /** 'amp'면 AMP의 AnalyserNode를 사용, 'raw'면 getUserMedia로 별도 스트림 열어 모니터 */
  mode: "amp" | "raw";
  /** raw 모드에서 사용할 deviceId */
  deviceId?: string;
  /** amp 모드에서 전달되는 AnalyserNode */
  ampAnalyser?: AnalyserNode | null;
  /** 높이(px) */
  height?: number;
  /** 클래스네임(선택) */
  className?: string;
};

export default function RecordingWaveScroll({
  active,
  mode,
  deviceId,
  ampAnalyser,
  height = 160,
  className,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);

  // raw 모드 전용 리소스
  const [ctx, setCtx] = useState<AudioContext | null>(null);
  const srcRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rawStreamRef = useRef<MediaStream | null>(null);

  // 캔버스 초기화
  const setupCanvas = () => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const W = cv.clientWidth * dpr;
    const H = height * dpr;
    if (cv.width !== Math.floor(W) || cv.height !== Math.floor(H)) {
      cv.width = Math.floor(W);
      cv.height = Math.floor(H);
    }
    const g = cv.getContext("2d");
    if (g) {
      g.fillStyle = "#0b1220";
      g.fillRect(0, 0, cv.width, cv.height);
    }
  };

  // raw 모드: 스트림 열고 analyser 구성
  async function openRawAnalyser() {
    if (ctx || analyserRef.current) return; // 이미 열려있음
    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext;
    const c = new Ctx();
    setCtx(c);

    const constraints = deviceId
      ? { audio: { deviceId: { exact: deviceId } as any } }
      : { audio: true };
    const stream = await navigator.mediaDevices.getUserMedia(constraints as any);
    rawStreamRef.current = stream;

    const src = c.createMediaStreamSource(stream);
    srcRef.current = src;

    const an = c.createAnalyser();
    an.fftSize = 2048;
    an.smoothingTimeConstant = 0.12;
    src.connect(an);
    analyserRef.current = an;
  }

  function closeRawAnalyser() {
    try { srcRef.current?.disconnect(); } catch {}
    analyserRef.current = null;
    srcRef.current = null;
    if (rawStreamRef.current) {
      rawStreamRef.current.getTracks().forEach(t => t.stop());
      rawStreamRef.current = null;
    }
    if (ctx) {
      try { ctx.close(); } catch {}
      setCtx(null);
    }
  }

  // 드로잉 루프(파형 스크롤)
  const draw = () => {
    const cv = canvasRef.current;
    if (!cv) return;
    const g = cv.getContext("2d");
    if (!g) return;

    // 사용할 analyser 결정
    const an =
      mode === "amp" ? (ampAnalyser || null) : (analyserRef.current || null);
    if (!an) {
      // 소스가 아직 없다면 화면만 유지
      g.fillStyle = "#0b1220";
      g.fillRect(0, 0, cv.width, cv.height);
      rafRef.current = requestAnimationFrame(draw);
      return;
    }

    // 기존 이미지를 한 픽셀 왼쪽으로 밀기
    g.drawImage(cv, -1, 0);

    // 오른쪽 1px 컬럼 지우기
    g.fillStyle = "#0b1220";
    g.fillRect(cv.width - 1, 0, 1, cv.height);

    // 파형 1열 그리기(상/하단 envelope)
    const buf = new Float32Array(an.fftSize);
    an.getFloatTimeDomainData(buf);

    // 한 열에 들어갈샘플 수를 적절히 집약 (여기선 8개씩 min/max)
    const step = 8;
    let min = 1, max = -1;
    for (let i = 0; i < buf.length; i += step) {
      let lmin = 1, lmax = -1;
      for (let k = 0; k < step && i + k < buf.length; k++) {
        const v = buf[i + k];
        if (v < lmin) lmin = v;
        if (v > lmax) lmax = v;
      }
      if (lmin < min) min = lmin;
      if (lmax > max) max = lmax;
    }

    const mid = Math.floor(cv.height / 2);
    const y1 = mid + Math.floor(min * (cv.height * 0.44));
    const y2 = mid + Math.floor(max * (cv.height * 0.44));

    // 컬러(Gradient)
    const grad = g.createLinearGradient(cv.width - 1, 0, cv.width - 1, cv.height);
    grad.addColorStop(0, "#60a5fa");
    grad.addColorStop(1, "#a78bfa");
    g.strokeStyle = grad;

    // 오른쪽 1px 세로선으로 상/하 경계 그리기
    g.beginPath();
    g.moveTo(cv.width - 1 + 0.5, y1 + 0.5);
    g.lineTo(cv.width - 1 + 0.5, y2 + 0.5);
    g.stroke();

    rafRef.current = requestAnimationFrame(draw);
  };

  // active/mode 변화 감시
  useEffect(() => {
    setupCanvas();

    if (!active) {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      if (mode === "raw") closeRawAnalyser();
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        if (mode === "raw") {
          await openRawAnalyser();
        } else {
          // amp 모드: 외부에서 전달된 analyser만 사용
          if (!ampAnalyser) return;
        }
        if (!cancelled) {
          if (rafRef.current) cancelAnimationFrame(rafRef.current);
          rafRef.current = requestAnimationFrame(draw);
        }
      } catch (e) {
        // 조용히 실패(권한 거부 등)
      }
    })();

    return () => {
      cancelled = true;
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      if (mode === "raw") closeRawAnalyser();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, mode, deviceId, ampAnalyser]);

  useEffect(() => {
    const onResize = () => setupCanvas();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className={className} style={{ background: "#0b1220", border: "1px dashed #1f2937", borderRadius: 12, padding: 8 }}>
      <canvas ref={canvasRef} style={{ width: "100%", height, display: "block" }} />
    </div>
  );
}