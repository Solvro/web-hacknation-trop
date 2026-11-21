// Kampanie / Śledztwa / Lab fixtures (filled in step 3–5).
import type { Operator } from '../contracts';
import { CAMPAIGNS, CAMPAIGN_STORY } from './universe';

export function campaignDetail(id: string) {
  const c = CAMPAIGNS.find((x) => x.id === id);
  if (!c) return undefined;
  const s = CAMPAIGN_STORY[id];
  return { ...c, description: s ? `${s.h1}\n${s.p}` : c.narrative, level: 'L2', counts: { incidents: c.n_incidents, domains: c.n_domains }, brands: [] };
}
export function campaignExtras(_id: string, _what: string): unknown { return undefined; }
export function mergePreview(_a: string, _b: string): unknown { return undefined; }
export const operators: Record<string, Operator> = {};
export const oracle: unknown[] = [];
export function actPackage(_id: string): unknown { return undefined; }
export const labMetrics: unknown = undefined;
export function trace(_t?: string, _v?: string): unknown { return undefined; }
export function investigations(_id: string): unknown { return undefined; }
export function links(a?: string, b?: string): unknown {
  const mk = (txt: string) => ({ type: 'tracking', field: 'x', value: txt, display: txt, strength: 'H', weight: 1 });
  const miss = { type: 'content', field: 'headline_template', value: '', display: 'treść i osoby: strona jest pusta', strength: 'L', weight: 0, state: 'missing' };
  if (a === 'INC-24768' && b === 'KMP-017') return { a, b, score_campaign: 5.4, score_operator: 6.7, p: 0.52, decision: 'triage', evidence: [mk('ta sama bramka CAPI'), mk('ten sam kit'), mk('domena .live z nocnym certyfikatem, jak 19 domen tej kampanii')], missing: [miss], conflicts: [], zeroed: [] };
  if (a === 'INC-24768' && b === 'KMP-034') return { a, b, score_campaign: 5.0, score_operator: 6.7, p: 0.47, decision: 'triage', evidence: [mk('ta sama bramka CAPI'), mk('ten sam kit'), mk('Oracle przypisał kelvaro.live do tej kampanii (0.64)')], missing: [miss], conflicts: [], zeroed: [] };
  return undefined;
}
