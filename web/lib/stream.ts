'use client';
// SSE consumer (CONTRACTS §4): EventSource on the same-origin proxy, `?replay=demo` passthrough,
// and a client-side simulation for offline demo (local-* job ids or API down).
import { useEffect, useRef } from 'react';
import type { Event } from './contracts';
import { API, isOffline } from './api';

export interface TimedEvent { delay: number; ev: Event }

const TYPES: Event['type'][] = [
  'job.step', 'job.evidence', 'job.finding', 'job.ranking', 'job.done', 'job.error',
  'agent.step', 'graph.node_added', 'graph.edge_added', 'casefile.delta', 'investigation.decision', 'investigation.done',
  'incident.created', 'incident.attributed', 'campaign.updated', 'oracle.match',
];
const TERMINAL = new Set(['job.done', 'investigation.done']);

export interface StreamOpts {
  /** path under /api/v1, e.g. `/jobs/JOB-1/stream` */
  path: string | null;
  replay?: boolean;
  /** events to play when the live stream is unavailable */
  simulate?: () => TimedEvent[];
  /** force simulation (local ids) */
  local?: boolean;
  speed?: number;
  onEvent: (ev: Event) => void;
  onSource?: (src: 'live' | 'replay' | 'simulated') => void;
}

export function useEventStream({ path, replay, simulate, local, speed = 1, onEvent, onSource }: StreamOpts) {
  const cb = useRef(onEvent);
  cb.current = onEvent;
  const srcCb = useRef(onSource);
  srcCb.current = onSource;

  useEffect(() => {
    if (!path) return;
    let closed = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let es: EventSource | null = null;

    const runSim = () => {
      if (!simulate) return;
      srcCb.current?.('simulated');
      let t = 0;
      for (const te of simulate()) {
        t += te.delay / speed;
        timers.push(setTimeout(() => { if (!closed) cb.current({ ...te.ev, at: new Date().toISOString() }); }, t));
      }
    };

    if (local || isOffline() || typeof EventSource === 'undefined') {
      runSim();
    } else {
      let got = false;
      const url = API + path + (replay ? (path.includes('?') ? '&' : '?') + 'replay=demo' : '');
      es = new EventSource(url);
      srcCb.current?.(replay ? 'replay' : 'live');
      const handle = (m: MessageEvent) => {
        got = true;
        try {
          const parsed = JSON.parse(m.data);
          const ev: Event = parsed && parsed.type && parsed.data ? parsed : { type: m.type as Event['type'], at: new Date().toISOString(), data: parsed };
          cb.current(ev);
          if (TERMINAL.has(ev.type)) { es?.close(); }
        } catch { /* ignore malformed */ }
      };
      for (const t of TYPES) es.addEventListener(t, handle as EventListener);
      es.onmessage = handle;
      es.onerror = () => {
        if (closed) return;
        if (!got) { es?.close(); es = null; runSim(); }
        // after events started, EventSource retries on its own; a finished stream is closed above.
      };
    }
    return () => { closed = true; es?.close(); timers.forEach(clearTimeout); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, replay, local, speed]);
}
