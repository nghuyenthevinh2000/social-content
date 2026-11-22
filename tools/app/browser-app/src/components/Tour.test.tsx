import { render } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';

import { Tour } from './Tour';

describe('Tour', () => {
  test('clamps tooltip inside viewport when target is taller than window', () => {
    const target = document.createElement('section');
    target.className = 'panel';
    target.getBoundingClientRect = () =>
      ({ top: -40, bottom: 850, left: 0, right: 400, width: 400, height: 890, x: 0, y: -40, toJSON: () => ({}) }) as DOMRect;
    document.body.appendChild(target);

    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    const { container } = render(
      <Tour
        steps={[{ target: 'section.panel', tab: 'video', title: 'Step 10', text: 'Tall target' }]}
        onTab={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const tip = container.querySelector('.tour-tip') as HTMLElement;
    expect(tip.style.top).toBe('16px');
    expect(tip.style.bottom).toBe('');
    target.remove();
  });

  test('highlights target while positioning tooltip around tipTarget', () => {
    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.getBoundingClientRect = () =>
      ({ top: -40, bottom: 850, left: 10, right: 410, width: 400, height: 890, x: 10, y: -40, toJSON: () => ({}) }) as DOMRect;
    const textarea = document.createElement('textarea');
    textarea.className = 'prompt-textarea';
    textarea.getBoundingClientRect = () =>
      ({ top: 300, bottom: 380, left: 20, right: 400, width: 380, height: 80, x: 20, y: 300, toJSON: () => ({}) }) as DOMRect;
    panel.appendChild(textarea);
    document.body.appendChild(panel);

    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    const { container } = render(
      <Tour
        steps={[{ target: 'section.panel', tipTarget: '.prompt-textarea', tab: 'video', title: 'Step 10', text: 'Around textarea' }]}
        onTab={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const spot = container.querySelector('.tour-spot') as HTMLElement;
    const tip = container.querySelector('.tour-tip') as HTMLElement;
    expect(spot.style.height).toBe('902px');
    expect(tip.style.top).toBe('396px');
    panel.remove();
  });
});
