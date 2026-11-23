import type { Card } from './card.ts';

/** An Instagram post's content (ig-post-designer's output shape). */
export interface Post {
  date?: string;
  title: string;
  sections: Array<{ label: string; lines: string[] }>;
}

export type PostTheme = 'whiteboard' | 'game-inspired' | 'clean';

export const POST_WIDTH = 1080;
export const POST_HEIGHT = 1350;

/** The day's card as a post: every section and its flow; the daily block is already gone. */
export function postFromCard(card: Card): Post {
  return {
    date: card.date,
    title: card.title,
    sections: card.sections.map((s) => ({ label: s.label, lines: s.flow ? [...s.lines, s.flow] : s.lines })),
  };
}

function esc(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const NBSP = ' ';

/**
 * Keep a measure together: "50 m · 4 lengths · 202 kg" never breaks across lines, nor does
 * a number and its unit.
 */
function glue(text: string): string {
  return text
    .replace(/ · /g, `${NBSP}·${NBSP}`)
    .replace(/(\d) (m|km|kg|s|reps|lengths?|rounds?|min|km\/h)\b/g, `$1${NBSP}$2`);
}

/** Greedy word wrap by an average glyph width; long words are split. */
function wrap(text: string, size: number, width: number): string[] {
  const max = Math.max(8, Math.floor(width / (size * 0.56)));
  const out: string[] = [];
  let line = '';
  for (const word of glue(text).split(/[ \t\n]+/).filter(Boolean)) {
    const pieces = word.length > max ? word.match(new RegExp(`.{1,${max}}`, 'g'))! : [word];
    for (const piece of pieces) {
      if (!line) line = piece;
      else if (line.length + 1 + piece.length <= max) line += ` ${piece}`;
      else {
        out.push(line);
        line = piece;
      }
    }
  }
  if (line) out.push(line);
  return out.map((l) => l.replaceAll(NBSP, ' '));
}

interface Look {
  background: string;
  board?: { x: number; y: number; w: number; h: number; fill: string; frame: string };
  text: string;
  heading: string;
  accent: string;
  font: string;
  titleShadow?: string;
  panel?: { fill: string; stroke: string };
  extras: string;
}

const FONT = "Inter, 'DejaVu Sans', Helvetica, Arial, sans-serif";

function look(theme: PostTheme): Look {
  switch (theme) {
    case 'whiteboard':
      return {
        background: '#cbd5e1',
        board: { x: 40, y: 40, w: POST_WIDTH - 80, h: POST_HEIGHT - 150, fill: '#ffffff', frame: '#9ca3af' },
        text: '#1e3a8a',
        heading: '#b91c1c',
        accent: '#15803d',
        font: FONT,
        // Marker tray under the board.
        extras: `<rect x="160" y="${POST_HEIGHT - 96}" width="${POST_WIDTH - 320}" height="34" rx="8" fill="#94a3b8"/>
<rect x="260" y="${POST_HEIGHT - 110}" width="120" height="16" rx="6" fill="#1e3a8a"/>
<rect x="400" y="${POST_HEIGHT - 110}" width="120" height="16" rx="6" fill="#b91c1c"/>`,
      };
    case 'game-inspired':
      return {
        background: 'url(#sunset)',
        text: '#111827',
        heading: '#111827',
        accent: '#7c2d12',
        font: FONT,
        titleShadow: '#111827',
        panel: { fill: '#fff7ed', stroke: '#111827' },
        extras: `<defs><linearGradient id="sunset" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#ff7e5f"/><stop offset="0.55" stop-color="#feb47b"/><stop offset="1" stop-color="#6a3093"/>
</linearGradient></defs>`,
      };
    case 'clean':
      return { background: '#0b0b0f', text: '#f9fafb', heading: '#22d3ee', accent: '#22d3ee', font: FONT, extras: '' };
  }
}

/**
 * The post as a 1080 x 1350 SVG. Headings are 40 px or more and lines 28 px or more, so it
 * reads on a phone; what does not fit ends with "+ more on the card".
 */
export function postSvg(post: Post, theme: PostTheme): string {
  const l = look(theme);
  const left = l.board ? l.board.x + 50 : 80;
  const width = l.board ? l.board.w - 100 : POST_WIDTH - 160;
  const bottom = l.board ? l.board.y + l.board.h - 40 : POST_HEIGHT - 80;
  const start = (l.board ? l.board.y : 0) + 70;

  // The largest text that fits without cutting anything; the smallest scale keeps the
  // phone-readable minimums (title 64, headings 42, lines 32).
  let laid = layout(1);
  for (const scale of [1.5, 1.35, 1.2]) {
    const tryIt = layout(scale);
    if (!tryIt.truncated) {
      laid = tryIt;
      break;
    }
  }
  const parts = laid.parts;

  function layout(scale: number): { parts: string[]; truncated: boolean } {
    const size = { title: Math.round(64 * scale), head: Math.round(42 * scale), line: Math.round(32 * scale) };
    const gap = { title: Math.round(size.title * 1.2), head: Math.round(size.head * 1.45), line: Math.round(size.line * 1.38) };
    const out: string[] = [];
    let y = start;
    if (post.date) {
      out.push(`<text x="${left}" y="${y}" font-size="30" fill="${l.accent}" font-family="${l.font}">${esc(post.date)}</text>`);
      y += 24;
    }
    y += size.title;
    for (const line of wrap(post.title, size.title, width).slice(0, 2)) {
      if (l.titleShadow) {
        out.push(`<text x="${left + 6}" y="${y + 6}" font-size="${size.title}" font-weight="900" fill="${l.titleShadow}" font-family="${l.font}">${esc(line)}</text>`);
      }
      out.push(`<text x="${left}" y="${y}" font-size="${size.title}" font-weight="900" fill="${l.heading}" font-family="${l.font}">${esc(line)}</text>`);
      y += gap.title;
    }
    y += 10;

    let truncated = false;
    for (const section of post.sections) {
      const lines = section.lines.flatMap((t) => wrap(t, size.line, width - 20));
      if (y + gap.head + gap.line > bottom) {
        truncated = true;
        break;
      }
      const top = y;
      const body: string[] = [];
      body.push(`<text x="${left}" y="${y + size.head}" font-size="${size.head}" font-weight="800" fill="${l.heading}" font-family="${l.font}">${esc(section.label)}</text>`);
      y += gap.head;
      for (const line of lines) {
        if (y + gap.line > bottom - 50) {
          truncated = true;
          break;
        }
        body.push(`<text x="${left + 20}" y="${y + size.line}" font-size="${size.line}" fill="${l.text}" font-family="${l.font}">${esc(line)}</text>`);
        y += gap.line;
      }
      y += 24;
      if (l.panel) {
        out.push(`<rect x="${left - 24}" y="${top}" width="${width + 48}" height="${y - top - 10}" rx="10" fill="${l.panel.fill}" stroke="${l.panel.stroke}" stroke-width="6"/>`);
      }
      out.push(...body);
      if (truncated) break;
    }
    if (truncated) {
      out.push(`<text x="${left}" y="${bottom}" font-size="30" fill="${l.accent}" font-family="${l.font}">+ more on the card</text>`);
    }
    return { parts: out, truncated };
  }

  const board = l.board
    ? `<rect x="${l.board.x - 14}" y="${l.board.y - 14}" width="${l.board.w + 28}" height="${l.board.h + 28}" rx="18" fill="${l.board.frame}"/>
<rect x="${l.board.x}" y="${l.board.y}" width="${l.board.w}" height="${l.board.h}" rx="6" fill="${l.board.fill}"/>`
    : '';
  const defs = l.extras.startsWith('<defs>') ? l.extras : '';
  const after = l.extras.startsWith('<defs>') ? '' : l.extras;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${POST_WIDTH}" height="${POST_HEIGHT}" viewBox="0 0 ${POST_WIDTH} ${POST_HEIGHT}">
${defs}<rect width="${POST_WIDTH}" height="${POST_HEIGHT}" fill="${l.background}"/>
${board}
${after}
${parts.join('\n')}
</svg>`;
}
