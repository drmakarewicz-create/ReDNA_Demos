export interface VirtualizerMetrics {
  total: number;
  visible: number;
}

export interface PerfMetricsSnapshot {
  virtualizers: Record<string, VirtualizerMetrics>;
}

type Listener = (snapshot: PerfMetricsSnapshot) => void;

const listeners = new Set<Listener>();
let cache: PerfMetricsSnapshot = { virtualizers: {} };

function emit() {
  for (const listener of listeners) {
    listener(cache);
  }
}

export function subscribePerfMetrics(listener: Listener): () => void {
  listeners.add(listener);
  listener(cache);
  return () => {
    listeners.delete(listener);
  };
}

export function updateVirtualizerMetrics(id: string, metrics: VirtualizerMetrics): void {
  const current = cache.virtualizers[id];
  if (current && current.total === metrics.total && current.visible === metrics.visible) {
    return;
  }
  cache = {
    virtualizers: {
      ...cache.virtualizers,
      [id]: metrics,
    },
  };
  emit();
}

export function removeVirtualizerMetrics(id: string): void {
  if (!(id in cache.virtualizers)) {
    return;
  }
  const next = { ...cache.virtualizers };
  delete next[id];
  cache = { virtualizers: next };
  emit();
}
