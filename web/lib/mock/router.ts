// Path → fixture resolver for the offline fallback. Mirrors the REST paths of docs/design §7.1 + CONTRACTS §5.
import { CAMPAIGNS, CAMPAIGN_STORY, DECISIONS, INCIDENTS } from './universe';
import { FOCUS, campaignCloud, focusIdFor } from './graph';
import { campaignDetail, campaignExtras, mergePreview, operators, oracle, actPackage, labMetrics, trace, investigations, links } from './kampanie';
import { SCENARIO_INCIDENT, scenarioFor } from './jobs';

type Json = unknown;

export function resolveGet(path: string, q: URLSearchParams): Json | undefined {
  const seg = path.replace(/^\/+|\/+$/g, '').split('/');
  const [a, b, c] = seg;
  switch (a) {
    case 'health':
      return { ok: true, mode: 'mock', db: 'fixture', redis: 'fixture', version: 'web-fixtures', counts: { incidents: 1284, campaigns: 41 } };
    case 'campaigns':
      if (!b) return CAMPAIGNS;
      if (!c) return campaignDetail(b);
      if (c === 'merge-preview') return mergePreview(b, q.get('other') ?? 'KMP-043');
      return campaignExtras(b, c);
    case 'operators':
      return b ? operators[b] : Object.values(operators);
    case 'incidents':
      if (!b) return Object.values(INCIDENTS);
      if (c === 'decision') return DECISIONS[b];
      if (!c) return INCIDENTS[b];
      return undefined;
    case 'links':
      return links(b, c);
    case 'graph': {
      const focus = q.get('focus');
      if (focus) {
        const origin = q.get('origin') ?? 'INC-24817';
        const key = focusIdFor(focus);
        if (key && FOCUS[key]) return FOCUS[key](origin);
        if (/^KMP-/.test(focus)) return campaignCloud(focus);
        return undefined;
      }
      return campaignCloud(q.get('campaign') ?? 'KMP-017');
    }
    case 'traces':
      return trace(b, decodeURIComponent(c ?? ''));
    case 'oracle':
      if (b === 'predictions') return oracle;
      return undefined;
    case 'act':
      if (b === 'packages' && c) return actPackage(c);
      return undefined;
    case 'investigations':
      return b ? investigations(b) : [investigations('INV-7')];
    case 'lab':
      return labMetrics;
    case 'stats':
      return { window: '24h', incidents: 1284, incidents_new: 37, campaigns_active: 41, operators: 6, domains_new: 9, oracle_flagged: 3, triage_open: 23, N: 1284 };
  }
  return undefined;
}

export function campaignStory(id: string) {
  return CAMPAIGN_STORY[id];
}

export function localAnalyze(input: string): { job_id: string; incident_id: string } {
  const sc = scenarioFor(input);
  return { job_id: `local-${sc}-${Date.now().toString(36)}`, incident_id: SCENARIO_INCIDENT[sc] };
}
