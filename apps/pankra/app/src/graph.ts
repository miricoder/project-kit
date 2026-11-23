import type { Core, ElementDefinition, NodeSingular, StylesheetStyle } from 'cytoscape';
import type { Edge, Provider } from '@pankra/shared';
import type { GraphNode } from './api';

/** "skill:result-analyzer" */
export const nodeId = (n: Pick<GraphNode, 'kind' | 'name'>) => `${n.kind}:${n.name}`;

const PROVIDER_LABELS: Record<Provider, string> = { claude: 'Claude', gpt: 'GPT' };

/**
 * Cytoscape elements for the registry: every node, the tools its edges name, and one box per
 * provider with dashed `runsOn` edges.
 */
export function graphElements(nodes: GraphNode[], edges: Edge[]): ElementDefinition[] {
  const elements: ElementDefinition[] = [];
  const ids = new Set<string>();
  const add = (id: string, data: Record<string, unknown>) => {
    if (ids.has(id)) return;
    ids.add(id);
    elements.push({ group: 'nodes', data: { id, ...data } });
  };

  for (const n of nodes) add(nodeId(n), { kind: n.kind, label: n.name, name: n.name });
  const providers = new Set<Provider>();
  for (const n of nodes) for (const p of Object.keys(n.providers) as Provider[]) providers.add(p);
  for (const p of providers) add(`provider:${p}`, { kind: 'provider', label: PROVIDER_LABELS[p] ?? p, name: p });

  let i = 0;
  for (const e of edges) {
    for (const end of [e.from, e.to]) {
      if (!ids.has(end) && end.startsWith('tool:')) add(end, { kind: 'tool', label: end.slice(5), name: end.slice(5) });
    }
    if (!ids.has(e.from) || !ids.has(e.to)) continue;
    elements.push({
      group: 'edges',
      data: { id: `e${i++}`, source: e.from, target: e.to, type: e.type, order: e.order, label: e.type === 'calls' && e.order ? String(e.order) : '' },
    });
  }
  for (const n of nodes) {
    for (const p of Object.keys(n.providers) as Provider[]) {
      elements.push({ group: 'edges', data: { id: `e${i++}`, source: nodeId(n), target: `provider:${p}`, type: 'runsOn', label: '' } });
    }
  }
  return elements;
}

/** Light up a node: an agent shows its skills numbered in run order; others their neighbours. */
function highlight(cy: Core, node: NodeSingular) {
  cy.batch(() => {
    cy.elements().addClass('dimmed');
    node.removeClass('dimmed').addClass('focus');
    if (node.data('kind') === 'agent') {
      node
        .outgoers('edge[type = "calls"]')
        .sort((a, b) => Number(a.data('order')) - Number(b.data('order')))
        .forEach((edge, idx) => {
          const order = Number(edge.data('order')) || idx + 1;
          edge.removeClass('dimmed').addClass('step');
          edge.target().removeClass('dimmed').addClass('step').data('step', order);
        });
    } else {
      node.connectedEdges().removeClass('dimmed').addClass('neighbour');
      node.neighborhood('node').removeClass('dimmed').addClass('neighbour');
    }
  });
}

function reset(cy: Core) {
  cy.batch(() => {
    cy.elements().removeClass('dimmed focus step neighbour');
    cy.nodes().removeData('step');
  });
}

/** Hover highlights, tap selects. Returns a function that removes the handlers. */
export function mountGraph(cy: Core, opts: { onSelect: (id: string) => void }): () => void {
  const over = (e: { target: NodeSingular }) => highlight(cy, e.target);
  const out = () => reset(cy);
  // Touch screens have no hover: a tap also lights the node up, a tap on the background clears.
  const tap = (e: { target: NodeSingular }) => {
    highlight(cy, e.target);
    const kind = e.target.data('kind');
    if (kind === 'skill' || kind === 'agent' || kind === 'plugin') opts.onSelect(e.target.id());
  };
  const background = (e: { target: unknown }) => {
    if (e.target === cy) reset(cy);
  };
  cy.on('mouseover', 'node', over);
  cy.on('mouseout', 'node', out);
  cy.on('tap', 'node', tap);
  cy.on('tap', background);
  return () => {
    cy.off('mouseover', 'node', over);
    cy.off('mouseout', 'node', out);
    cy.off('tap', 'node', tap);
    cy.off('tap', background);
  };
}

/** Neo4j-Browser-like look: skill circle, agent large circle, plugin double ring, provider box. */
export const GRAPH_STYLE: StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': 11,
      color: '#111827',
      'text-valign': 'bottom',
      'text-margin-y': 4,
      'background-color': '#94a3b8',
      width: 34,
      height: 34,
    },
  },
  { selector: 'node[kind = "skill"]', style: { shape: 'ellipse', 'background-color': '#57c7e3' } },
  { selector: 'node[kind = "agent"]', style: { shape: 'ellipse', width: 56, height: 56, 'background-color': '#f79767' } },
  {
    selector: 'node[kind = "plugin"]',
    style: { shape: 'ellipse', width: 50, height: 50, 'background-color': '#d9c8ae', 'border-width': 6, 'border-style': 'double', 'border-color': '#8b7355' },
  },
  { selector: 'node[kind = "provider"]', style: { shape: 'round-rectangle', width: 70, height: 30, 'background-color': '#c990c0', 'text-valign': 'center', 'text-margin-y': 0 } },
  { selector: 'node[kind = "tool"]', style: { shape: 'round-rectangle', width: 18, height: 18, 'background-color': '#d1d5db', 'font-size': 9 } },
  { selector: 'edge', style: { width: 1.5, 'line-color': '#9ca3af', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#9ca3af', 'curve-style': 'bezier', label: 'data(label)', 'font-size': 10 } },
  { selector: 'edge[type = "runsOn"]', style: { 'line-style': 'dashed', 'target-arrow-shape': 'none' } },
  { selector: 'edge[type = "contains"]', style: { 'line-color': '#c4b5a0', 'target-arrow-color': '#c4b5a0' } },
  { selector: '.dimmed', style: { opacity: 0.15 } },
  { selector: 'node.focus', style: { 'border-width': 4, 'border-color': '#111827' } },
  { selector: 'node.step', style: { label: (n: NodeSingular) => `${n.data('step')}. ${n.data('label')}`, 'font-weight': 'bold', 'border-width': 3, 'border-color': '#f79767' } },
  { selector: 'edge.step', style: { width: 3, 'line-color': '#f79767', 'target-arrow-color': '#f79767' } },
  { selector: 'node.neighbour', style: { 'border-width': 2, 'border-color': '#111827' } },
];
