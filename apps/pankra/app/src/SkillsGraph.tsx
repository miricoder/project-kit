'use dom';

// An Expo DOM component: rendered inline on the web, inside a WebView on iPhone, with the
// same Cytoscape code on both.
import cytoscape from 'cytoscape';
import { useEffect, useRef } from 'react';
import type { DOMProps } from 'expo/dom';
import type { Edge } from '@pankra/shared';
import type { GraphNode } from './api';
import { GRAPH_STYLE, graphElements, mountGraph } from './graph';

export default function SkillsGraph({ nodes, edges, onSelect }: {
  nodes: GraphNode[];
  edges: Edge[];
  onSelect: (id: string) => Promise<void>;
  dom?: DOMProps;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({
      container: container.current,
      elements: graphElements(nodes, edges),
      style: GRAPH_STYLE,
      layout: { name: 'cose', animate: false, padding: 24, nodeRepulsion: () => 9000 },
      wheelSensitivity: 0.3,
    });
    const unmount = mountGraph(cy, { onSelect: (id) => void onSelect(id) });
    return () => {
      unmount();
      cy.destroy();
    };
  }, [nodes, edges, onSelect]);

  return (
    <div
      ref={container}
      role="img"
      aria-label="Graph of skills, agents, plugins and providers. The list below has the same nodes."
      style={{ width: '100%', height: '100%', minHeight: 420, background: '#fafaf9', borderRadius: 12 }}
    />
  );
}
