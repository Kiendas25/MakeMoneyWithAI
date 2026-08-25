import type {FC} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {CelText, CYAN, GOLD, INK, LABEL, MONO, PAPER, PINK, Screentone} from '../anime/kit';
import {Sfx} from '../anime/Sfx';

const CARD = {x: 540, y: 900};

// Each annotation draws a leader line out from the card, then types its label.
const NOTES = [
  {label: 'SaaS', at: 26, left: 80, width: 300, y: 545, side: 'left' as const, color: PINK},
  {label: 'API', at: 52, left: 700, width: 300, y: 645, side: 'right' as const, color: CYAN},
  {label: 'CONSULTING', at: 78, left: 80, width: 440, y: 1325, side: 'left' as const, color: GOLD},
];

// The leader line terminates at the label's inner edge.
const tipOf = (n: (typeof NOTES)[number]) => ({
  x: n.side === 'left' ? n.left + n.width : n.left,
  y: n.y,
});

export const MonetizeAnnotation: FC = () => {
  const frame = useCurrentFrame();

  const cardIn = interpolate(frame, [0, 12], [0.86, 1], {
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });
  const darken = interpolate(frame, [120, 150], [0, 0.28], {extrapolateLeft: 'clamp'});
  const underline = interpolate(frame, [104, 122], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });

  return (
    <AbsoluteFill style={{background: PAPER, overflow: 'hidden'}}>
      <Sfx cues={[{src: 'Typing.mp3', atFrame: 26, volume: 0.45}]} />

      <Screentone color={INK} size={12} radius={2.2} opacity={0.1} />

      {/* Leader lines are drawn beneath the card so they emerge from its edge. */}
      <svg width={1080} height={1920} viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0}}>
        {NOTES.map((note) => {
          const draw = interpolate(frame, [note.at, note.at + 12], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: (v) => 1 - Math.pow(1 - v, 3),
          });
          const tip = tipOf(note);
          const x = CARD.x + (tip.x - CARD.x) * draw;
          const y = CARD.y + (tip.y - CARD.y) * draw;
          return (
            <g key={note.label}>
              <line
                x1={CARD.x}
                y1={CARD.y}
                x2={x}
                y2={y}
                stroke={INK}
                strokeWidth={7}
                strokeLinecap="round"
              />
              {draw > 0.98 ? <circle cx={x} cy={y} r={14} fill={note.color} stroke={INK} strokeWidth={5} /> : null}
            </g>
          );
        })}
      </svg>

      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div
          style={{
            transform: `scale(${cardIn}) rotate(-2deg)`,
            background: INK,
            border: `10px solid ${INK}`,
            borderRadius: 26,
            boxShadow: `20px 20px 0 ${PINK}`,
            padding: '54px 64px',
            textAlign: 'center',
          }}
        >
          <div style={{fontFamily: MONO, fontWeight: 700, fontSize: 82, color: PAPER}}>ollama</div>
          <div
            style={{
              fontFamily: LABEL,
              fontSize: 48,
              color: GOLD,
              marginTop: 14,
              letterSpacing: '0.1em',
            }}
          >
            ★ 153.4k
          </div>
        </div>
      </AbsoluteFill>

      {/* Typed labels */}
      {NOTES.map((note) => {
        const typeStart = note.at + 12;
        const chars = Math.round(
          interpolate(frame, [typeStart, typeStart + note.label.length * 1.8], [0, note.label.length], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
        );
        if (chars <= 0) return null;
        const shown = note.label.slice(0, chars);
        return (
          <div
            key={note.label}
            style={{
              position: 'absolute',
              left: note.left,
              top: note.y - 52,
              width: note.width,
              boxSizing: 'border-box',
              textAlign: 'center',
              fontFamily: LABEL,
              fontSize: note.label.length > 6 ? 54 : 66,
              color: INK,
              background: note.color,
              border: `7px solid ${INK}`,
              borderRadius: 14,
              padding: '10px 12px',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
            }}
          >
            {shown}
          </div>
        );
      })}

      <div style={{position: 'absolute', top: 150, width: '100%', display: 'flex', justifyContent: 'center'}}>
        <div style={{position: 'relative'}}>
          <CelText size={82} color={INK} outline={PAPER} shadow={`${PINK}00`} strokeWidth={10}>
            {'HOW PEOPLE\nACTUALLY MONETIZE IT'}
          </CelText>
          <div
            style={{
              position: 'absolute',
              bottom: -18,
              left: 0,
              height: 18,
              width: `${underline * 100}%`,
              background: GOLD,
              border: `4px solid ${INK}`,
              borderRadius: 8,
            }}
          />
        </div>
      </div>

      <AbsoluteFill style={{background: INK, opacity: darken}} />
    </AbsoluteFill>
  );
};
