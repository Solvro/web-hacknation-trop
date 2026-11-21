'use client';
// Small real image of a material (its ad screenshot, else the landing render). Renders nothing when the API has none.
import { useArtifacts } from '@/lib/artifacts';

export function MaterialThumb({ id, className = 'w-12 h-12' }: { id: string; className?: string }) {
  const art = useArtifacts(id);
  if (!art.any) return null;
  return <img src={art.ad ?? art.any} alt="" loading="lazy" className={className + ' flex-none object-cover object-top rounded-lg border border-line1 bg-bg2'} />;
}
