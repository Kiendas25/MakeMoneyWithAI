// Clock abstraction so the detector/engine pipeline is identical live vs.
// backtest. Live uses wall time; backtest uses a virtual clock advanced by the
// replay driver — never Date.now() — which makes runs deterministic.

export interface Clock {
  now(): number; // epoch ms
}

export class WallClock implements Clock {
  now(): number {
    return Date.now();
  }
}

export class VirtualClock implements Clock {
  constructor(private t: number) {}
  now(): number {
    return this.t;
  }
  set(ms: number): void {
    this.t = ms;
  }
  advance(ms: number): void {
    this.t += ms;
  }
}
