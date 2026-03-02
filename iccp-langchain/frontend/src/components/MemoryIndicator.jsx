function MemoryIndicator({ count = 0, items = [], title = '记忆召回' }) {
  const safeItems = Array.isArray(items) ? items : []

  return (
    <div className="mb-4 space-y-2">
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary/10 border text-primary text-xs">
        {title} {count} 条
      </div>
      {safeItems.length > 0 ? (
        <div className="rounded-md border bg-muted p-3 space-y-2">
          <p className="text-xs text-foreground">召回明细</p>
          {safeItems.slice(0, 3).map((item) => (
            <div
              key={item.id || `${item.source_module}-${item.memory_type}-${item.score}`}
              className="text-xs text-foreground border rounded-md p-2 bg-card"
            >
              <p className="text-primary">
                来源：{item.source_module || '-'} · 类型：{item.memory_type || '-'} · 分数：{item.score ?? '-'}
              </p>
              <p className="mt-1 text-muted-foreground whitespace-pre-wrap">{(item.content || '').slice(0, 180)}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default MemoryIndicator
