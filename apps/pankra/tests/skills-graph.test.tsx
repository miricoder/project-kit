import cytoscape from 'cytoscape';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import { graphElements, mountGraph } from '../app/src/graph.ts';
import type { GraphNode } from '../app/src/api.ts';
import { RunPanel } from '../app/src/RunPanel.tsx';
import type { CredentialStatus, Edge } from '../packages/shared/src/index.ts';
import { REF, REPO, fakeGitHub } from './helpers/fake-github.ts';

/** The Skills screen's data: the real registry, synced through the API. */
async function skillsScreenData() {
  const store = new MemoryStore();
  const app = buildApp({
    store,
    userId: () => 'owner',
    now: () => new Date('2026-11-23T12:00:00Z'),
    fetch: fakeGitHub().fetchImpl,
    registry: { repo: REPO, ref: REF },
  });
  expect((await app.inject({ method: 'POST', url: '/api/v1/registry/sync' })).statusCode).toBe(200);
  const nodes = (await app.inject({ method: 'GET', url: '/api/v1/nodes' })).json() as GraphNode[];
  const edges = (await app.inject({ method: 'GET', url: '/api/v1/edges' })).json() as Edge[];
  return { nodes, edges };
}

/** Open the Skills screen: the graph mounted on a real (headless) Cytoscape instance. */
async function openSkillsScreen() {
  const { nodes, edges } = await skillsScreenData();
  const cy = cytoscape({ headless: true, styleEnabled: true, elements: graphElements(nodes, edges) });
  const selected: string[] = [];
  mountGraph(cy, { onSelect: (id) => selected.push(id) });
  return { cy, nodes, selected };
}

describe('Registry and skills graph', () => {
  it('Scenario: hovering an agent shows its run order', async () => {
    // Given the Skills screen is open
    const { cy } = await openSkillsScreen();
    expect(cy.nodes('[kind = "skill"], [kind = "agent"], [kind = "plugin"]')).toHaveLength(13);

    // When the athlete hovers weekly-coach
    cy.$id('agent:weekly-coach').emit('mouseover');

    // Then its 3 skills are highlighted and numbered 1 to 3
    const steps = cy.nodes('.step').map((n) => [n.id(), n.data('step')]);
    expect(steps.sort((a, b) => Number(a[1]) - Number(b[1]))).toEqual([
      ['skill:purposed-convo-workout-readjust', 1],
      ['skill:schedule-shifter', 2],
      ['skill:workout-whiteboard', 3],
    ]);
    expect(cy.$id('agent:weekly-coach').hasClass('focus')).toBe(true);

    // And every other node is dimmed
    const lit = new Set(['agent:weekly-coach', ...steps.map((s) => String(s[0]))]);
    for (const n of cy.nodes()) {
      expect(n.hasClass('dimmed'), n.id()).toBe(!lit.has(n.id()));
    }

    // Moving off restores the graph.
    cy.$id('agent:weekly-coach').emit('mouseout');
    expect(cy.elements('.dimmed, .step, .focus')).toHaveLength(0);
  });

  it('Scenario: clicking a node opens its run panel', async () => {
    // Given the Skills screen is open
    const { cy, nodes, selected } = await openSkillsScreen();

    // When the athlete clicks race-analyzer
    cy.$id('skill:race-analyzer').emit('tap');
    expect(selected).toEqual(['skill:race-analyzer']);
    const node = nodes.find((n) => `${n.kind}:${n.name}` === selected[0])!;

    // Then a panel shows its description, provider choice, credential status and a Run button
    const credentials: CredentialStatus[] = [{ provider: 'gpt', last4: 'abcd', retention: '7d', expiresAt: null }];
    // React separates adjacent text parts with <!-- --> when rendering to a string.
    const html = renderToString(createElement(RunPanel, { node, credentials, input: {} })).replace(/<!-- -->/g, '');
    expect(html).toContain(node.description);
    const group = html.match(/<div[^>]*role="radiogroup"[^>]*>/)?.[0] ?? '';
    expect(group).toContain('aria-label="Provider"');
    expect(html.match(/role="radio"/g)).toHaveLength(2);
    expect(html).toContain('Claude · claude-sonnet-5-5');
    expect(html).toContain('GPT · gpt-5');
    expect(html).toContain('Needs a Claude key');
    expect(html).toMatch(/role="button"[^>]*>(<[^>]+>)*Run</);
  });
});
