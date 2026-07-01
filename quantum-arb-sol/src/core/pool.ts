// Minimal free-list object pool for the detector hot path. Reusing Quote-array
// scratch buffers avoids per-tick allocation churn (GC pause mitigation). Gains
// are only claimed after the --bench harness shows them; this stays optional.

export class FreeList<T> {
  private readonly items: T[] = [];

  constructor(
    private readonly factory: () => T,
    private readonly reset: (item: T) => void,
    prealloc = 0,
  ) {
    for (let i = 0; i < prealloc; i++) this.items.push(factory());
  }

  acquire(): T {
    const it = this.items.pop();
    return it ?? this.factory();
  }

  release(item: T): void {
    this.reset(item);
    this.items.push(item);
  }

  get size(): number {
    return this.items.length;
  }
}
