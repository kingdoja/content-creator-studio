const FLOW_ORDER = ['route', 'react', 'reflection', 'plan_solve', 'rag', 'quality_gate', 'reflection_refine', 'finalize']

function nodeState(node, visitedSet) {
  if (visitedSet.has(node)) return 'visited'
  return 'idle'
}

function NodeCard({ label, state }) {
  const stateClass =
    state === 'visited'
      ? 'bg-primary/10 border-primary/40 text-primary'
      : 'bg-muted border text-muted-foreground'
  return (
    <div className={`px-3 py-2 rounded-md text-xs font-medium ${stateClass}`}>
      {label}
    </div>
  )
}

function AgentFlowVisualization({ trace = [] }) {
  const visitedSet = new Set()
  trace.forEach((item) => {
    if (typeof item !== 'string') return
    if (item.startsWith('node:')) visitedSet.add(item.replace('node:', ''))
    if (item.startsWith('route:')) visitedSet.add('route')
    if (item.startsWith('execute:')) visitedSet.add(item.replace('execute:', ''))
    if (item.startsWith('quality_gate:')) visitedSet.add('quality_gate')
    if (item === 'finalize') visitedSet.add('finalize')
  })

  return (
    <div className="bg-muted border rounded-md p-4">
      <p className="text-xs text-muted-foreground mb-3">Agent 执行可视化</p>
      <div className="flex flex-wrap gap-2">
        {FLOW_ORDER.map((node) => (
          <NodeCard key={node} label={node} state={nodeState(node, visitedSet)} />
        ))}
      </div>
    </div>
  )
}

export default AgentFlowVisualization
