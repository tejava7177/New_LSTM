import React from 'react';

type Props = {
  title: React.ReactNode;
  defaultOpen?: boolean;
  rightSlot?: React.ReactNode;       // 요약줄 오른쪽 상태/버튼
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  variant?: 'light' | 'dark';         // ★ 추가: 테마 전환
  className?: string;                 // ★ 추가: 외부에서 클래스 보강
};

export default function Accordion({
  title,
  defaultOpen = false,
  rightSlot,
  onOpenChange,
  children,
  variant = 'light',
  className = '',
}: Props) {
  const [open, setOpen] = React.useState(defaultOpen);
  const onToggle = (e: React.SyntheticEvent<HTMLDetailsElement>) => {
    const isOpen = (e.target as HTMLDetailsElement).open;
    setOpen(isOpen);
    onOpenChange?.(isOpen);
  };

  return (
    <details className={`acc ${className}`} data-variant={variant} open={open} onToggle={onToggle}>
      <summary className="acc-sum">
        <span className="acc-title">{title}</span>
        <span className="acc-right">{rightSlot}</span>
      </summary>
      <div className="acc-body">{children}</div>

      {/* local styles */}
      <style>{String.raw`
        /* 공통 */
        .acc {
          border:1px solid var(--acc-border);
          border-radius:12px;
          background:var(--acc-bg);
          color:var(--acc-text);
        }
        .acc-sum {
          list-style:none; cursor:pointer; user-select:none;
          display:flex; align-items:center; gap:10px; padding:10px 12px;
          transition: background-color .15s ease;
        }
        .acc-sum::-webkit-details-marker { display:none; }
        .acc:hover .acc-sum { background: var(--acc-hover); }
        .acc:focus-within { outline:2px solid var(--acc-ring); outline-offset:2px; }
        .acc-title { font-weight:600; color:var(--acc-text); }
        .acc-right { margin-left:auto; color:var(--acc-muted); font-size:12px; }
        .acc-body { padding:12px; border-top:1px solid var(--acc-border); background:var(--acc-body); }

        /* 라이트 테마 */
        .acc[data-variant="light"]{
          --acc-bg:#ffffff;
          --acc-body:#ffffff;
          --acc-border:#e5e7eb;
          --acc-text:#111827;
          --acc-muted:#6b7280;
          --acc-hover:#f8fafc;
          --acc-ring:#93c5fd;
        }

        /* 다크 테마(기존 스타일) */
        .acc[data-variant="dark"]{
          --acc-bg:#0b1220;
          --acc-body:#0b1220;
          --acc-border:#1f2937;
          --acc-text:#e5e7eb;
          --acc-muted:#9ca3af;
          --acc-hover:#111827;
          --acc-ring:#1d4ed8;
        }
      `}</style>
    </details>
  );
}