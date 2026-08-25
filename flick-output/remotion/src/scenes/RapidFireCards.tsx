import type {FC} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {
  CelText,
  CYAN,
  GOLD,
  INK,
  ImpactFlash,
  LABEL,
  PAPER,
  PINK,
  Screentone,
  SpeedLines,
  slamIn,
} from '../anime/kit';
import {Sfx} from '../anime/Sfx';

const HOLD = 33;
const CARDS = [
  {name: 'AutoGPT', stars: '178.8k', accent: GOLD, from: 'left' as const, seed: 3},
  {name: 'Ollama', stars: '153.4k', accent: CYAN, from: 'right' as const, seed: 9},
  {name: 'LangChain', stars: '116.5k', accent: PINK, from: 'top' as const, seed: 17},
  {name: 'n8n', stars: '143.7k', accent: GOLD, from: 'left' as const, seed: 23},
  {name: 'ComfyUI', stars: '89.8k', accent: CYAN, from: 'right' as const, seed: 31},
];

const offsetFor = (from: 'left' | 'right' | 'top', k: number) => {
  if (from === 'left') return `translateX(${-k * 900}px)`;
  if (from === 'right') return `translateX(${k * 900}px)`;
  return `translateY(${-k * 900}px)`;
};

export const RapidFireCards: FC = () => {
  const frame = useCurrentFrame();
  const index = Math.min(CARDS.length - 1, Math.floor(frame / HOLD));
  const card = CARDS[index];
  const local = frame - index * HOLD;

  // Hard cut, no cross-fade: each card is fully replaced on its beat.
  const entry = slamIn(local, 0, {overshoot: 1.2, settle: 9});
  const slideK = interpolate(local, [0, 7], [1, 0], {
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 4),
  });
  const rush = interpolate(local, [0, 10], [0.2, 1], {extrapolateRight: 'clamp'});
  const split = interpolate(local, [0, 5], [18, 0], {extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{background: INK, overflow: 'hidden'}}>
      <Sfx cues={CARDS.map((_, i) => ({src: 'Pop.mp3', atFrame: i * HOLD, volume: 0.6}))} />

      <Screentone color={card.accent} size={15} radius={2.8} opacity={0.12} drift={0.4} />
      <SpeedLines
        count={90}
        color={card.accent}
        seed={card.seed}
        progress={rush}
        inner={280}
        opacity={0.4}
      />

      <AbsoluteFill
        style={{
          alignItems: 'center',
          justifyContent: 'center',
          transform: `${offsetFor(card.from, slideK)} scale(${entry.scale})`,
          opacity: entry.opacity,
        }}
      >
        <div
          style={{
            background: PAPER,
            border: `12px solid ${INK}`,
            borderRadius: 30,
            boxShadow: `26px 26px 0 ${card.accent}`,
            padding: '80px 70px',
            minWidth: 820,
            textAlign: 'center',
          }}
        >
          <div
            style={{
              fontFamily: LABEL,
              fontSize: 44,
              letterSpacing: '0.28em',
              color: INK,
              opacity: 0.55,
              marginBottom: 34,
            }}
          >
            {String(index + 1).padStart(2, '0')} / 05
          </div>

          <div style={{display: 'flex', justifyContent: 'center'}}>
            <CelText
              size={card.name.length > 8 ? 132 : 168}
              color={INK}
              outline={card.accent}
              shadow={card.accent}
              split={split}
              strokeWidth={12}
            >
              {card.name}
            </CelText>
          </div>

          <div
            style={{
              marginTop: card.name.length > 8 ? 175 : 215,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 16,
            }}
          >
            <svg width={64} height={64} viewBox="0 0 24 24">
              <path
                d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.3 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8z"
                fill={GOLD}
                stroke={INK}
                strokeWidth={1.8}
                strokeLinejoin="round"
              />
            </svg>
            <div style={{fontFamily: LABEL, fontSize: 72, color: INK}}>{card.stars}</div>
          </div>
        </div>
      </AbsoluteFill>

      {CARDS.map((_, i) => (
        <ImpactFlash key={i} at={i * HOLD} duration={3} color="#fff" />
      ))}
    </AbsoluteFill>
  );
};
