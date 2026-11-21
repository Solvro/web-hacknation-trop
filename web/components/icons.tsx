// Inline stroke icons (24 viewBox, currentColor, aria-hidden) as on the boards.
import type { SVGProps } from 'react';

const base = (p: SVGProps<SVGSVGElement>, w = 1.8) => ({
  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: w, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const,
  'aria-hidden': true, width: 16, height: 16, ...p,
});

export const IArrow = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 2.2)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
export const IImage = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M4 5h16v14H4zM4 15l4-4 4 4 3-3 5 5" /></svg>;
export const IVideo = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M4 6h11v12H4zM15 10l5-3v10l-5-3" /></svg>;
export const IFile = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M6 3h8l4 4v14H6zM14 3v4h4" /></svg>;
export const ISearch = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0M16 16l5 5" /></svg>;
export const IList = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 1.9)}><path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" /></svg>;
export const IGraph = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 1.9)}><path d="M6 6m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M18 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M6 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M8 7l8 4M8 17l8-4" /></svg>;
export const ICheck = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 3)}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>;
export const IChev = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 2)}><path d="M6 9l6 6 6-6" /></svg>;
export const IChevR = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 2)}><path d="M9 6l6 6-6 6" /></svg>;
export const IX = (p: SVGProps<SVGSVGElement>) => <svg {...base(p, 2)}><path d="M6 6l12 12M18 6L6 18" /></svg>;
export const IDownload = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>;
export const IUpload = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 20V9M7 14l5-5 5 5M5 4h14" /></svg>;
