import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { KnowledgeGraph as KnowledgeGraphData } from '../types'

interface SimNode {
  id: string
  label: string
  category: string
  x: number
  y: number
  vx: number
  vy: number
  fx: number | null
  fy: number | null
  degree: number
}

interface KnowledgeGraphProps {
  data: KnowledgeGraphData
  onSelect: (id: string, label: string) => void
}

// d3.schemeTableau10 — keep the web client's palette for visual parity.
const TABLEAU10 = [
  '#4e79a7',
  '#f28e2c',
  '#e15759',
  '#76b7b2',
  '#59a14f',
  '#edc949',
  '#af7aa1',
  '#ff9da7',
  '#9c755f',
  '#bab0ab',
]

const nodeRadius = (degree: number) => Math.max(4, Math.min(12, 4 + degree * 1.4))

// A dependency-free force-directed graph with wheel zoom, canvas pan and node
// drag. The physics loop writes positions DIRECTLY to the DOM (like d3) instead
// of calling setState per frame, so React never re-renders during the
// simulation — this is what keeps it from flickering.
const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ data, onSelect }) => {
  const wrapRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const sizeRef = useRef({ w: 800, h: 560 })
  const [hover, setHover] = useState<string | null>(null)
  // Bumping this re-arms the physics loop (used while dragging) without
  // rebuilding the model, preserving current node positions.
  const [warmTick, setWarmTick] = useState(0)

  // View transform (pan + zoom).
  const viewRef = useRef({ k: 1, x: 0, y: 0 })

  // Build the immutable model once per data change.
  const model = useMemo(() => {
    const degree = new Map<string, number>()
    data.links.forEach((l) => {
      degree.set(l.source, (degree.get(l.source) || 0) + 1)
      degree.set(l.target, (degree.get(l.target) || 0) + 1)
    })
    const categories = Array.from(new Set(data.nodes.map((n) => n.category || 'default')))
    const colorOf = (cat: string) => TABLEAU10[categories.indexOf(cat) % TABLEAU10.length]

    const n = data.nodes.length || 1
    const { w, h } = sizeRef.current
    const cx = w / 2
    const cy = h / 2
    const nodes: SimNode[] = data.nodes.map((nd, i) => {
      const angle = (i / n) * Math.PI * 2
      const radius = Math.min(w, h) * 0.32
      return {
        id: nd.id,
        label: nd.label,
        category: nd.category || 'default',
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
        fx: null,
        fy: null,
        degree: degree.get(nd.id) || 0,
      }
    })
    const valid = new Set(nodes.map((x) => x.id))
    const byId = new Map(nodes.map((x) => [x.id, x]))
    const links = data.links
      .filter((l) => valid.has(l.source) && valid.has(l.target))
      .map((l, i) => ({ key: i, a: byId.get(l.source)!, b: byId.get(l.target)! }))
    const adjacency = new Map<string, Set<string>>()
    data.links.forEach((l) => {
      if (!valid.has(l.source) || !valid.has(l.target)) return
      if (!adjacency.has(l.source)) adjacency.set(l.source, new Set())
      if (!adjacency.has(l.target)) adjacency.set(l.target, new Set())
      adjacency.get(l.source)!.add(l.target)
      adjacency.get(l.target)!.add(l.source)
    })
    return { nodes, links, adjacency, categories, colorOf, byId }
  }, [data])

  // DOM refs for imperative position updates.
  const rootRef = useRef<SVGGElement>(null)
  const lineEls = useRef(new Map<number, SVGLineElement>())
  const groupEls = useRef(new Map<string, SVGGElement>())

  // Track container size in a ref; never triggers a re-render on its own.
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const apply = () => {
      sizeRef.current = { w: el.clientWidth || 800, h: el.clientHeight || 560 }
    }
    apply()
    const ro = new ResizeObserver(apply)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Physics loop. Restarts only when the model (data) changes. Writes to DOM.
  // Uses d3-style alpha cooling so it always settles and stops the rAF.
  useEffect(() => {
    const { nodes, links } = model
    if (nodes.length === 0) return
    let raf = 0
    let alive = true
    // Global cooling factor; decays toward 0 and scales how far nodes move.
    let alpha = 1
    const alphaDecay = 0.018
    const alphaMin = 0.005

    const paint = () => {
      links.forEach(({ key, a, b }) => {
        const el = lineEls.current.get(key)
        if (!el) return
        el.setAttribute('x1', String(a.x))
        el.setAttribute('y1', String(a.y))
        el.setAttribute('x2', String(b.x))
        el.setAttribute('y2', String(b.y))
      })
      nodes.forEach((node) => {
        const el = groupEls.current.get(node.id)
        if (el) el.setAttribute('transform', `translate(${node.x},${node.y})`)
      })
    }

    const step = () => {
      if (!alive) return
      const { w, h } = sizeRef.current
      const cx = w / 2
      const cy = h / 2
      const repulsion = 9000
      const springLen = 80
      const spring = 0.04
      const centering = 0.012
      const dragging = nodes.some((node) => node.fx != null)

      // Reset accumulated velocity each tick (alpha-scaled displacement) so the
      // system can't accumulate energy and oscillate.
      nodes.forEach((node) => {
        node.vx = 0
        node.vy = 0
      })

      // Repulsion + collision: nodes push apart, never overlap their radii.
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        const ra = nodeRadius(a.degree)
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]
          let dx = a.x - b.x
          let dy = a.y - b.y
          let d2 = dx * dx + dy * dy
          if (d2 < 0.01) {
            dx = Math.random() - 0.5
            dy = Math.random() - 0.5
            d2 = 0.01
          }
          let d = Math.sqrt(d2)
          let f = repulsion / d2
          // Hard collision: strongly separate if closer than combined radii.
          const minDist = ra + nodeRadius(b.degree) + 14
          if (d < minDist) f += (minDist - d) * 0.6
          a.vx += (dx / d) * f
          a.vy += (dy / d) * f
          b.vx -= (dx / d) * f
          b.vy -= (dy / d) * f
        }
      }
      links.forEach(({ a, b }) => {
        const dx = b.x - a.x
        const dy = b.y - a.y
        const d = Math.sqrt(dx * dx + dy * dy) || 1
        const f = (d - springLen) * spring
        a.vx += (dx / d) * f
        a.vy += (dy / d) * f
        b.vx -= (dx / d) * f
        b.vy -= (dy / d) * f
      })
      // Weak centering so the whole graph stays in view without collapsing.
      nodes.forEach((node) => {
        node.vx += (cx - node.x) * centering
        node.vy += (cy - node.y) * centering
      })

      // Apply alpha-scaled displacement; pinned nodes stay put. Cap per-tick
      // movement so strong initial forces don't fling nodes off-screen.
      const maxStep = 30
      nodes.forEach((node) => {
        if (node.fx != null) {
          node.x = node.fx
          node.y = node.fy as number
          return
        }
        let dx = node.vx * alpha
        let dy = node.vy * alpha
        const m = Math.hypot(dx, dy)
        if (m > maxStep) {
          dx = (dx / m) * maxStep
          dy = (dy / m) * maxStep
        }
        node.x += dx
        node.y += dy
      })

      paint()
      alpha += (0 - alpha) * alphaDecay
      // Keep running while cooling, or while a node is being dragged.
      if (alpha > alphaMin || dragging) {
        raf = requestAnimationFrame(step)
      }
    }
    raf = requestAnimationFrame(step)
    return () => {
      alive = false
      cancelAnimationFrame(raf)
    }
    // warmTick re-arms the loop on demand (e.g. while dragging) without
    // rebuilding the model, so positions are preserved.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model, warmTick])

  // Apply the view transform imperatively (no re-render needed).
  const applyView = () => {
    const v = viewRef.current
    if (rootRef.current) rootRef.current.setAttribute('transform', `translate(${v.x},${v.y}) scale(${v.k})`)
  }
  useEffect(applyView)

  // Convert a pointer event to graph (pre-transform) coordinates.
  const toGraph = (clientX: number, clientY: number) => {
    const rect = svgRef.current!.getBoundingClientRect()
    const v = viewRef.current
    return { x: (clientX - rect.left - v.x) / v.k, y: (clientY - rect.top - v.y) / v.k }
  }

  // Wheel zoom centered on the cursor (matches d3.zoom scaleExtent [0.2, 5]).
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const v = viewRef.current
    const rect = svgRef.current!.getBoundingClientRect()
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top
    const factor = Math.exp(-e.deltaY * 0.0015)
    const k = Math.min(5, Math.max(0.2, v.k * factor))
    viewRef.current = { k, x: px - ((px - v.x) / v.k) * k, y: py - ((py - v.y) / v.k) * k }
    applyView()
  }

  // Drag: on a node moves the node, on background pans the canvas.
  const dragRef = useRef<
    | { mode: 'node'; node: SimNode; moved: boolean }
    | { mode: 'pan'; startX: number; startY: number; ox: number; oy: number }
    | null
  >(null)
  const kick = () => setWarmTick((v) => v + 1)

  const onPointerDownNode = (e: React.PointerEvent, node: SimNode) => {
    e.stopPropagation()
    ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
    const p = toGraph(e.clientX, e.clientY)
    node.fx = p.x
    node.fy = p.y
    dragRef.current = { mode: 'node', node, moved: false }
    kick()
  }

  const onPointerDownBg = (e: React.PointerEvent) => {
    ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
    const v = viewRef.current
    dragRef.current = { mode: 'pan', startX: e.clientX, startY: e.clientY, ox: v.x, oy: v.y }
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const drag = dragRef.current
    if (!drag) return
    if (drag.mode === 'node') {
      const p = toGraph(e.clientX, e.clientY)
      drag.node.fx = p.x
      drag.node.fy = p.y
      drag.moved = true
      // Keep the loop warm for live dragging.
      const el = groupEls.current.get(drag.node.id)
      if (el) el.setAttribute('transform', `translate(${p.x},${p.y})`)
    } else {
      viewRef.current = { k: viewRef.current.k, x: drag.ox + (e.clientX - drag.startX), y: drag.oy + (e.clientY - drag.startY) }
      applyView()
    }
  }

  const onPointerUp = (e: React.PointerEvent, node?: SimNode) => {
    const drag = dragRef.current
    if (drag?.mode === 'node') {
      drag.node.fx = null
      drag.node.fy = null
      if (node && !drag.moved) onSelect(node.id, node.label)
      kick()
    }
    dragRef.current = null
    try {
      ;(e.target as Element).releasePointerCapture(e.pointerId)
    } catch {
      /* noop */
    }
  }

  const { nodes, links, adjacency, categories, colorOf } = model
  const { w, h } = sizeRef.current
  const isDimmed = (id: string) => hover != null && hover !== id && !adjacency.get(hover)?.has(id)
  const isLinkActive = (aId: string, bId: string) => hover === aId || hover === bId

  return (
    <div ref={wrapRef} className="w-full h-full relative overflow-hidden">
      <svg
        ref={svgRef}
        width={w}
        height={h}
        className="select-none block cursor-grab active:cursor-grabbing"
        onWheel={onWheel}
        onPointerDown={onPointerDownBg}
        onPointerMove={onPointerMove}
        onPointerUp={(e) => onPointerUp(e)}
      >
        <g ref={rootRef}>
          {links.map(({ key, a, b }) => {
            const active = isLinkActive(a.id, b.id)
            return (
              <line
                key={key}
                ref={(el) => {
                  if (el) lineEls.current.set(key, el)
                  else lineEls.current.delete(key)
                }}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="#94a3b8"
                strokeOpacity={hover ? (active ? 0.8 : 0.1) : 0.3}
                strokeWidth={1}
              />
            )
          })}
          {nodes.map((n) => {
            const r = nodeRadius(n.degree)
            const dim = isDimmed(n.id)
            return (
              <g
                key={n.id}
                ref={(el) => {
                  if (el) groupEls.current.set(n.id, el)
                  else groupEls.current.delete(n.id)
                }}
                transform={`translate(${n.x},${n.y})`}
                className="cursor-pointer"
                opacity={dim ? 0.2 : 1}
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover(null)}
                onPointerDown={(e) => onPointerDownNode(e, n)}
                onPointerUp={(e) => onPointerUp(e, n)}
              >
                <circle r={r} fill={colorOf(n.category)} stroke="#fff" strokeWidth={1.5} />
                {(hover === n.id || n.degree >= 3) && (
                  <text x={r + 4} y={3} className="fill-content-secondary" fontSize={9} style={{ pointerEvents: 'none' }}>
                    {n.label.length > 15 ? n.label.slice(0, 14) + '…' : n.label}
                  </text>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      {/* Category legend, mirrors the web client. */}
      {categories.length > 0 && (
        <div className="absolute bottom-3 left-3 flex flex-wrap gap-x-3 gap-y-1 max-w-[60%] rounded-lg bg-surface px-3 py-2 border border-subtle shadow-sm">
          {categories.map((cat) => (
            <span key={cat} className="inline-flex items-center gap-1.5 text-[11px] text-content-secondary">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: colorOf(cat) }} />
              {cat}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default KnowledgeGraph
