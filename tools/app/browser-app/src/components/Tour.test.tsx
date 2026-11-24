import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, test, vi } from 'vitest';

import Home from '../pages/Home';

import { Tour } from './Tour';

describe('Tour', () => {
  afterEach(() => {
    delete (globalThis as Record<string, unknown>).__E2E_TEST_USER__;
    localStorage.clear();
    vi.restoreAllMocks();
  });

  test('clamps tooltip inside viewport when target is taller than window', () => {
    const target = document.createElement('section');
    target.className = 'panel';
    target.getBoundingClientRect = () =>
      ({
        top: -40,
        bottom: 850,
        left: 0,
        right: 400,
        width: 400,
        height: 890,
        x: 0,
        y: -40,
        toJSON: () => ({}),
      }) as DOMRect;
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
      ({
        top: -40,
        bottom: 850,
        left: 10,
        right: 410,
        width: 400,
        height: 890,
        x: 10,
        y: -40,
        toJSON: () => ({}),
      }) as DOMRect;
    const textarea = document.createElement('textarea');
    textarea.className = 'prompt-textarea';
    textarea.getBoundingClientRect = () =>
      ({
        top: 300,
        bottom: 380,
        left: 20,
        right: 400,
        width: 380,
        height: 80,
        x: 20,
        y: 300,
        toJSON: () => ({}),
      }) as DOMRect;
    panel.appendChild(textarea);
    document.body.appendChild(panel);

    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    const { container } = render(
      <Tour
        steps={[
          {
            target: 'section.panel',
            tipTarget: '.prompt-textarea',
            tab: 'video',
            title: 'Step 10',
            text: 'Around textarea',
          },
        ]}
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

  test('skips scrollIntoView when target is already in viewport and scrolls when offscreen', () => {
    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });

    const visible = document.createElement('div');
    visible.className = 'visible-target';
    visible.getBoundingClientRect = () =>
      ({
        top: 700,
        bottom: 740,
        left: 0,
        right: 300,
        width: 300,
        height: 40,
        x: 0,
        y: 700,
        toJSON: () => ({}),
      }) as DOMRect;
    const visibleScroll = vi.fn();
    visible.scrollIntoView = visibleScroll;
    document.body.appendChild(visible);

    const { unmount } = render(
      <Tour
        steps={[{ target: '.visible-target', tab: 'analyzer', title: 'Step 3', text: 'In viewport' }]}
        onTab={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(visibleScroll).not.toHaveBeenCalled();
    unmount();
    visible.remove();

    const offscreen = document.createElement('div');
    offscreen.className = 'offscreen-target';
    offscreen.getBoundingClientRect = () =>
      ({
        top: 900,
        bottom: 940,
        left: 0,
        right: 300,
        width: 300,
        height: 40,
        x: 0,
        y: 900,
        toJSON: () => ({}),
      }) as DOMRect;
    const offscreenScroll = vi.fn();
    offscreen.scrollIntoView = offscreenScroll;
    document.body.appendChild(offscreen);

    render(
      <Tour
        steps={[{ target: '.offscreen-target', tab: 'analyzer', title: 'Step 4', text: 'Offscreen' }]}
        onTab={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(offscreenScroll).toHaveBeenCalledWith({ block: 'center' });
    offscreen.remove();
  });

  test('walks through all 21 Home tour steps with matching DOM targets', async () => {
    (globalThis as Record<string, unknown>).__E2E_TEST_USER__ = {
      uid: 'uid_tour_walkthrough',
      email: 'tour@example.com',
      displayName: 'Tour Tester',
      providerData: [],
      getIdToken: async () => 'tok',
    };
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ok: true, topics: [], jobs: [], reels: [], media: [], balance: 0 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <Home />
      </MemoryRouter>,
    );

    for (let step = 1; step <= 21; step++) {
      await waitFor(() => {
        expect(screen.getByText(`${step}/21`)).toBeInTheDocument();
        expect(container.querySelector('.tour-spot')).not.toBeNull();
      });
      if (step === 4) {
        expect(document.querySelector('#results-analysis > div.source-breakdown')).not.toBeNull();
      }
      if (step === 6) {
        expect(document.querySelector('#results-analysis .keyword-meta')).not.toBeNull();
        expect(document.querySelector('#results-analysis .keyword-subpanel-head')).not.toBeNull();
      }
      if (step === 7) {
        expect(document.querySelector('#results-analysis > .sheet')).not.toBeNull();
        expect(document.querySelector('#results-analysis .reel-card-foot .topic-run-btn')).not.toBeNull();
      }
      if (step === 8) {
        expect(document.querySelector('#results-analysis details.reel-analysis-details')).not.toBeNull();
        expect(document.querySelector('#results-analysis .reel-player-box')).not.toBeNull();
      }
      if (step === 21) {
        expect(document.querySelector('section.panel.profile > button.profile-btn[aria-pressed]')).not.toBeNull();
      }
      if (step < 21) {
        fireEvent.click(screen.getByRole('button', { name: 'Tiếp' }));
      } else {
        fireEvent.click(screen.getByRole('button', { name: 'Xong' }));
      }
    }

    expect(container.querySelector('.tour')).toBeNull();
  });
});
