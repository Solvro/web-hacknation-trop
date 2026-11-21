// Path → fixture resolver for the offline fallback. Mirrors the REST paths of docs/design §7.1 + CONTRACTS §5.
import { CAMPAIGNS, CAMPAIGN_STORY, DECISIONS, INCIDENTS } from './universe';
import { FOCUS, campaignCloud, focusIdFor } from './graph';
import { campaignDetail, campaignExtras, mergePreview, operators, oracle, actPackage, packages, labMetrics, trace, investigations, links } from './kampanie';
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
      if (b === 'predictions') return oracle.filter((x) => !q.get('campaign') || x.campaign_id === q.get('campaign'));
      return undefined;
    case 'act':
      if (b === 'packages' && c) return actPackage(c);
      if (b === 'packages') return packages.filter((x) => !q.get('campaign_id') || x.campaign_id === q.get('campaign_id'));
      return undefined;
    case 'investigations':
      return b ? investigations(b) : [investigations('INV-7')];
    case 'lab':
      if (b === 'ablation') return [['tracking', -0.12], ['kit', -0.09], ['infra', -0.17], ['content', -0.05], ['persons', -0.02]].map(([layer, delta_f1]) => ({ layer, delta_f1 }));
      if (q.get('view') === 'baselines') return { view: 'baselines', model_version: 'engine@fixture', data: { sample: true, rows: [{ model: 'M1 (uczony)', bcubed_f1: 0.91 }, { model: 'ręczne wagi', bcubed_f1: 0.78 }, { model: 'HDBSCAN', bcubed_f1: 0.61 }] } };
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
