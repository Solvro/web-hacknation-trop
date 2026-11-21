// X1 EvidenceChip [TYP][wartość][siła][waga][rzadkość] (rp.css `.ev`).
import type { EvidenceItem } from '@/lib/contracts';
import { LAYER_LABEL, botName, n, w1 } from '@/lib/copy';

export function EvidenceChip({ e, big, onClick }: { e: EvidenceItem; big?: boolean; onClick?: () => void }) {
  const cls = ['ev', `t-${e.type}`, big ? 'big' : '', e.state === 'conflict' ? 'conf' : '', e.state === 'missing' ? 'miss' : '', e.state === 'zero' ? 'zero' : ''].join(' ');
  const s = e.strength === 'H' ? 'h' : e.strength === 'M' ? 'm' : 'l';
  const title = `${LAYER_LABEL[e.type]} · ${e.field} · ${e.value}${e.N ? ` · widziane w ${n(e.df ?? 0)} z ${n(e.N)}` : ''}${e.idf ? ` · idf ${e.idf.toFixed(2)}` : ''}${e.bot ? ` · znalazł ${botName(e.bot)}` : ''}`;
  const body = (
    <>
      <span className="t">{LAYER_LABEL[e.type]}</span>
      <span className="v">{e.state === 'missing' ? 'brak' : e.display}</span>
      <span className={`sb ${s}`} aria-label={`siła ${e.strength}`}><i /><i /><i /></span>
      <span className="w">{e.state === 'missing' ? '—' : w1(e.weight)}</span>
      {e.N && e.state !== 'missing' ? <span className="r">{n(e.df ?? 0)}/{n(e.N)}</span> : null}
    </>
  );
  if (onClick) return <button type="button" className={cls + ' cursor-pointer hover:border-line3'} title={title} onClick={onClick}>{body}</button>;
  return <span className={cls} title={title}>{body}</span>;
}
