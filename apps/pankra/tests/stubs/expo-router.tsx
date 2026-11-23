// Navigation is not what the component tests check: Link renders as a plain anchor.
import { createElement, type ReactNode } from 'react';

export function Link({ href, children }: { href: unknown; children?: ReactNode }) {
  return createElement('a', { href: typeof href === 'string' ? href : '#' }, children);
}
