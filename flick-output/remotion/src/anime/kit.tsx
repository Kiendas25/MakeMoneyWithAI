import type {CSSProperties, FC, ReactNode} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

export const INK = '#0d0b14';
export const PAPER = '#f4efe4';
export const PINK = '#ff2e63';
export const CYAN = '#22d3ee';
export const GOLD = '#ffc53d';

export const DISPLAY = '"Anton", "Liberation Sans", sans-serif';
export const LABEL = '"ArchivoBlack", "Liberation Sans", sans-serif';
export const MONO = '"DejaVu Sans Mono", monospace';

/**
 * Seeded PRNG. Remotion renders frames across parallel workers, so every
 * particle position has to be derived from a fixed seed rather than
 * Math.random — otherwise the field re-scatters on each frame.
 */
export const rng = (seed: number) => {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

/** Anime overshoot: fast in, past the mark, settle back. */
export const slamIn = (frame: number, at: number, {overshoot = 1.28, settle = 12} = {}) => {
  const t = frame - at;
  if (t < 0) return {scale: 0, opacity: 0};
  if (t < 3) return {scale: overshoot + (3 - t) * 0.5, opacity: t / 3};
  const scale = interpolate(t, [3, settle], [overshoot, 1], {
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });
  return {scale, opacity: 1};
};

export const Screentone: FC<{
  color?: string;
  size?: number;
  radius?: number;
  opacity?: number;
  drift?: number;
}> = ({color = '#000', size = 14, radius = 2.6, opacity = 0.16, drift = 0}) => {
  const frame = useCurrentFrame();
  const shift = (frame * drift) % size;
  return (
    <AbsoluteFill style={{opacity, transform: `translate(${shift}px, ${-shift}px)`}}>
      <svg width="120%" height="120%" style={{marginLeft: -size, marginTop: -size}}>
        <defs>
          <pattern id={`tone-${size}-${radius}`} width={size} height={size} patternUnits="userSpaceOnUse">
            <circle cx={size / 2} cy={size / 2} r={radius} fill={color} />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#tone-${size}-${radius})`} />
      </svg>
    </AbsoluteFill>
  );
};

/** Radial speed lines — the core anime energy cue. */
export const SpeedLines: FC<{
  count?: number;
  color?: string;
  seed?: number;
  progress?: number;
  cx?: number;
  cy?: number;
  inner?: number;
  opacity?: number;
}> = ({count = 90, color = '#fff', seed = 7, progress = 1, cx = 540, cy = 960, inner = 260, opacity = 1}) => {
  const rand = rng(seed);
  const lines = new Array(count).fill(0).map(() => {
    const angle = rand() * Math.PI * 2;
    const width = 3 + rand() * 16;
    const start = inner + rand() * 220;
    const len = 320 + rand() * 900;
    return {angle, width, start, len};
  });
  return (
    <AbsoluteFill style={{opacity}}>
      <svg width={1080} height={1920} viewBox="0 0 1080 1920">
        {lines.map((l, i) => {
          const reach = l.start + l.len * progress;
          const x1 = cx + Math.cos(l.angle) * l.start;
          const y1 = cy + Math.sin(l.angle) * l.start;
          const x2 = cx + Math.cos(l.angle) * reach;
          const y2 = cy + Math.sin(l.angle) * reach;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={color}
              strokeWidth={l.width}
              strokeLinecap="round"
            />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

/** Rotating cel-shaded sunburst wedges. */
export const Sunburst: FC<{
  color?: string;
  wedges?: number;
  speed?: number;
  cx?: number;
  cy?: number;
  opacity?: number;
}> = ({color = GOLD, wedges = 18, speed = 0.25, cx = 540, cy = 960, opacity = 0.5}) => {
  const frame = useCurrentFrame();
  const step = 360 / wedges;
  return (
    <AbsoluteFill style={{opacity}}>
      <svg width={1080} height={1920} viewBox="0 0 1080 1920">
        <g transform={`rotate(${frame * speed} ${cx} ${cy})`}>
          {new Array(wedges).fill(0).map((_, i) => {
            const a0 = ((i * step) * Math.PI) / 180;
            const a1 = ((i * step + step / 2) * Math.PI) / 180;
            const R = 2400;
            return (
              <polygon
                key={i}
                fill={color}
                points={`${cx},${cy} ${cx + Math.cos(a0) * R},${cy + Math.sin(a0) * R} ${cx + Math.cos(a1) * R},${cy + Math.sin(a1) * R}`}
              />
            );
          })}
        </g>
      </svg>
    </AbsoluteFill>
  );
};

/** Hard white/colour impact frame — the anime cut punctuation. */
export const ImpactFlash: FC<{at: number; duration?: number; color?: string}> = ({
  at,
  duration = 4,
  color = '#fff',
}) => {
  const frame = useCurrentFrame();
  const t = frame - at;
  if (t < 0 || t > duration) return null;
  const opacity = interpolate(t, [0, duration], [1, 0], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: color, opacity}} />;
};

/** Cel-shaded display text: heavy outline, hard offset shadow, optional RGB split. */
export const CelText: FC<{
  children: ReactNode;
  size: number;
  color?: string;
  outline?: string;
  shadow?: string;
  split?: number;
  font?: string;
  style?: CSSProperties;
  strokeWidth?: number;
  align?: 'left' | 'center' | 'right';
}> = ({
  children,
  size,
  color = PAPER,
  outline = INK,
  shadow = PINK,
  split = 0,
  font = DISPLAY,
  style,
  strokeWidth,
  align = 'left',
}) => {
  const sw = strokeWidth ?? Math.max(6, size * 0.055);
  const base: CSSProperties = {
    fontFamily: font,
    fontSize: size,
    lineHeight: 0.95,
    letterSpacing: '-0.01em',
    textTransform: 'uppercase',
    margin: 0,
    whiteSpace: 'pre',
    textAlign: align,
  };
  // The stacked layers are absolutely positioned, so they need an explicit
  // width for textAlign to have anything to align against.
  const layer: CSSProperties = {...base, position: 'absolute', width: '100%'};
  return (
    <div style={{position: 'relative', ...style}}>
      {split > 0 ? (
        <>
          <div style={{...layer, left: -split, top: 0, color: CYAN, opacity: 0.85}}>{children}</div>
          <div style={{...layer, left: split, top: 0, color: PINK, opacity: 0.85}}>{children}</div>
        </>
      ) : null}
      <div style={{...layer, left: sw * 0.9, top: sw * 0.9, color: shadow}}>{children}</div>
      <div
        style={{
          ...layer,
          left: 0,
          top: 0,
          color: 'transparent',
          WebkitTextStroke: `${sw}px ${outline}`,
          paintOrder: 'stroke',
        }}
      >
        {children}
      </div>
      <div style={{...base, position: 'relative', color}}>{children}</div>
    </div>
  );
};

/** Drifting petals — deterministic, seeded. */
export const Petals: FC<{count?: number; seed?: number; color?: string; opacity?: number}> = ({
  count = 26,
  seed = 21,
  color = PINK,
  opacity = 0.7,
}) => {
  const frame = useCurrentFrame();
  const rand = rng(seed);
  const petals = new Array(count).fill(0).map(() => ({
    x: rand() * 1080,
    y: rand() * 1920,
    r: 8 + rand() * 16,
    speed: 0.6 + rand() * 1.6,
    sway: 20 + rand() * 60,
    phase: rand() * Math.PI * 2,
    spin: (rand() - 0.5) * 4,
  }));
  return (
    <AbsoluteFill style={{opacity}}>
      <svg width={1080} height={1920} viewBox="0 0 1080 1920">
        {petals.map((p, i) => {
          const y = (p.y + frame * p.speed) % 2040 - 60;
          const x = p.x + Math.sin(frame * 0.03 + p.phase) * p.sway;
          return (
            <ellipse
              key={i}
              cx={x}
              cy={y}
              rx={p.r}
              ry={p.r * 0.55}
              fill={color}
              transform={`rotate(${frame * p.spin} ${x} ${y})`}
            />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
