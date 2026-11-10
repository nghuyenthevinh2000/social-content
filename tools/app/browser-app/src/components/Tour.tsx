import { useEffect, useState } from 'react';
import './Tour.css';

export type TourStep = { target: string; tab: string; title: string; text: string };

const PAD = 6;

/** Transparent spotlight box over each target + a tooltip; steps may switch tabs via onTab. */
export function Tour({ steps, onTab, onClose }: { steps: TourStep[]; onTab: (tab: string) => void; onClose: () => void }): React.ReactElement {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const step = steps[i];

  useEffect(() => {
    onTab(step.tab);
    // ponytail: polling (target mounts after tab switch / async load); swap for a MutationObserver if it matters
    const measure = () => setRect(document.querySelector(step.target)?.getBoundingClientRect() ?? null);
    document.querySelector(step.target)?.scrollIntoView({ block: 'center' });
    measure();
    const t = setInterval(measure, 150);
    return () => clearInterval(t);
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  const last = i === steps.length - 1;
  const below = rect ? rect.bottom + 190 < window.innerHeight : true;
  const tipStyle: React.CSSProperties = rect
    ? { top: below ? rect.bottom + PAD + 10 : undefined, bottom: below ? undefined : window.innerHeight - rect.top + PAD + 10 }
    : { top: '35%' };

  return (
    <div className="tour" role="dialog" aria-label="Hướng dẫn sử dụng">
      <div className="tour-blocker" onClick={onClose} />
      {rect && (
        <div
          className="tour-spot"
          style={{ top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }}
        />
      )}
      <div className="tour-tip" style={tipStyle}>
        <strong>{step.title}</strong>
        <p>{step.text}</p>
        <div className="tour-actions">
          <small>
            {i + 1}/{steps.length}
          </small>
          <button type="button" className="ghost small" onClick={onClose}>
            Bỏ qua
          </button>
          {i > 0 && (
            <button type="button" className="ghost small" onClick={() => setI(i - 1)}>
              Trước
            </button>
          )}
          <button type="button" className="primary small" onClick={() => (last ? onClose() : setI(i + 1))}>
            {last ? 'Xong' : 'Tiếp'}
          </button>
        </div>
      </div>
    </div>
  );
}
