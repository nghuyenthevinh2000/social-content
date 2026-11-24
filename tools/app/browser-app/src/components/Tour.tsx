import { useEffect, useState } from 'react';

import { useLocale } from '../locales';
import './Tour.css';

export type TourStep = {
  target: string;
  tipTarget?: string;
  tab: string;
  title: string;
  text: string;
  onEnter?: () => void;
};

const PAD = 6;
const sameRect = (a: DOMRect | null, b: DOMRect | null) =>
  a === b || (!!a && !!b && a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height);

/** Transparent spotlight box over each target + a tooltip; steps may switch tabs via onTab. */
export function Tour({
  steps,
  onTab,
  onClose,
}: {
  steps: TourStep[];
  onTab: (tab: string) => void;
  onClose: () => void;
}): React.ReactElement {
  const { t } = useLocale();
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [tipRect, setTipRect] = useState<DOMRect | null>(null);
  const step = steps[i];

  useEffect(() => {
    onTab(step.tab);
    step.onEnter?.();
    let scrolled = false;
    // ponytail: polling (target mounts after tab switch / async load); swap for a MutationObserver if it matters
    const measure = () => {
      const el = document.querySelector(step.target);
      const tipEl = step.tipTarget ? document.querySelector(step.tipTarget) : el;
      const scrollEl = tipEl ?? el;
      if (!scrolled && scrollEl) {
        scrolled = true;
        const r = scrollEl.getBoundingClientRect();
        if (r.top < 0 || r.bottom > window.innerHeight) {
          scrollEl.scrollIntoView?.({ block: 'center' });
        }
      }
      const nextRect = el ? el.getBoundingClientRect() : null;
      const nextTipRect = tipEl ? tipEl.getBoundingClientRect() : nextRect;
      setRect((prev) => (sameRect(prev, nextRect) ? prev : nextRect));
      setTipRect((prev) => (sameRect(prev, nextTipRect) ? prev : nextTipRect));
    };
    measure();
    const t = setInterval(measure, 150);
    return () => clearInterval(t);
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  const last = i === steps.length - 1;
  const gap = PAD + 10;
  const tipH = 240;
  const tipStyle: React.CSSProperties = !tipRect
    ? { top: '35%' }
    : tipRect.bottom + tipH < window.innerHeight
      ? { top: Math.max(gap, tipRect.bottom + gap) }
      : tipRect.top - gap - tipH > 0
        ? { bottom: window.innerHeight - tipRect.top + gap }
        : { top: Math.max(gap, Math.min(tipRect.top + gap, window.innerHeight - tipH)) };

  return (
    <div className="tour" role="dialog" aria-label={t.tour.dialogAria}>
      <div className="tour-blocker" onClick={onClose} />
      {rect && (
        <div
          className="tour-spot"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
          }}
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
            {t.tour.skip}
          </button>
          {i > 0 && (
            <button type="button" className="ghost small" onClick={() => setI(i - 1)}>
              {t.tour.prev}
            </button>
          )}
          <button type="button" className="primary small" onClick={() => (last ? onClose() : setI(i + 1))}>
            {last ? t.tour.done : t.tour.next}
          </button>
        </div>
      </div>
    </div>
  );
}
