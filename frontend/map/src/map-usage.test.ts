import { describe, expect, it } from 'vitest';

import { recordMapSessionUsage } from './map-usage';

describe('recordMapSessionUsage', () => {
  it('records a first map visit once per browser session', () => {
    const storage = new MapStorage();
    const sessionStorage = new MapStorage();

    expect(recordMapSessionUsage(storage, sessionStorage)).toEqual({ isReturning: false, visitCount: 1 });
    expect(recordMapSessionUsage(storage, sessionStorage)).toBeNull();
  });

  it('identifies a later browser session as returning without exposing an identifier', () => {
    const storage = new MapStorage();
    recordMapSessionUsage(storage, new MapStorage());

    expect(recordMapSessionUsage(storage, new MapStorage())).toEqual({ isReturning: true, visitCount: 2 });
  });

  it('caps the reported visit count', () => {
    const storage = new MapStorage();
    storage.setItem('undersun-map-visit-count', '20');

    expect(recordMapSessionUsage(storage, new MapStorage())).toEqual({ isReturning: true, visitCount: 9 });
  });
});

class MapStorage implements Storage {
  private readonly values = new Map<string, string>();

  get length() { return this.values.size; }
  clear() { this.values.clear(); }
  getItem(key: string) { return this.values.get(key) || null; }
  key(index: number) { return [...this.values.keys()][index] || null; }
  removeItem(key: string) { this.values.delete(key); }
  setItem(key: string, value: string) { this.values.set(key, value); }
}
