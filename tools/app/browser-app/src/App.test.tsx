import { render } from '@testing-library/react';
import React from 'react';
import { afterEach, describe, expect, test, vi } from 'vitest';

import App from './App';
import { apiJson } from './api';

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('renders without crashing', () => {
    const { baseElement } = render(<App />);
    expect(baseElement).toBeDefined();
  });

  test('apiJson parses valid JSON response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true, topics: [{ name: 'Test' }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const data = await apiJson('/api/sources/topics');
    expect(data).toEqual({ ok: true, topics: [{ name: 'Test' }] });
  });

  test('apiJson safely handles empty 200 response without Unexpected end of JSON error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 200 }));
    const data = await apiJson('/api/sources/topics');
    expect(data).toEqual({});
  });

  test('apiJson handles 502 Bad Gateway proxy failure with readable error message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 502, statusText: 'Bad Gateway' }));
    await expect(apiJson('/api/sources/topics')).rejects.toThrow(
      'Không thể kết nối đến máy chủ backend (127.0.0.1:8765)',
    );
  });

  test('apiJson handles error payload from server', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: 'Thiếu tên chủ đề' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await expect(apiJson('/api/sources/topics')).rejects.toThrow('Thiếu tên chủ đề');
  });
});
