import React from 'react';

type Props = {
  title: React.ReactNode;
  defaultOpen?: boolean;
  rightSlot?: React.ReactNode;     // 요약줄 오른쪽에 상태/버튼 등 넣고 싶을 때
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
};

export default function Accordion({ title, defaultOpen=false, rightSlot, onOpenChange, children }: Props) {
  const [open, setOpen] = React.useState(defaultOpen);
  const onToggle = (e: React.SyntheticEvent<HTMLDetailsElement>) => {
    const isOpen = (e.target as HTMLDetailsElement).open;
    setOpen(isOpen);
    onOpenChange?.(isOpen);
  };

  return (
    <details className="acc" open={open} onToggle={onToggle}>
      <summary className="acc-sum">
        <span className="acc-title">{title}</span>
        <span className="acc-right">{rightSlot}</span>
      </summary>
      <div className="acc-body">{children}</div>

      {/* local styles (필요시 전역 CSS로 옮겨도 됨) */}
      <style>{String.raw`
        .acc { border:1px solid #1f2937; border-radius:12px; background:#0b1220; }
        .acc-sum {
          list-style:none; cursor:pointer; user-select:none;
          display:flex; align-items:center; gap:10px; padding:10px 12px;
        }
        .acc-sum::-webkit-details-marker { display:none; }
        .acc-title { font-weight:600; color:#e5e7eb; }
        .acc-right { margin-left:auto; color:#9ca3af; font-size:12px; }
        .acc-body { padding:12px; border-top:1px solid #1f2937; }
      `}</style>
    </details>
  );
}