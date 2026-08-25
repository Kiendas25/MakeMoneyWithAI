import type {FC} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {CelText, INK, LABEL, PAPER, PINK, Screentone} from '../anime/kit';
import {Sfx} from '../anime/Sfx';

const CARDS = 6;
const SCAN_START = 18;
const SCAN_END = 92;
const SLASH = 100;

export const EmptyToolbox: FC = () => {
  const frame = useCurrentFrame();

  // The card row tracks past camera-left while the scanline hunts for content.
  const drift = interpolate(frame, [0, 135], [120, -300]);
  const scanY = interpolate(frame, [SCAN_START, SCAN_END], [820, 1240], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const scanOn = frame >= SCAN_START && frame <= SCAN_END + 8;

  // The slash is drawn, not faded — a hard ink stroke across the whole row.
  const slash = interpolate(frame, [SLASH, SLASH + 9], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });
  const shake = frame >= SLASH && frame < SLASH + 6 ? Math.sin(frame * 4) * 9 : 0;

  return (
    <AbsoluteFill style={{background: INK, overflow: 'hidden'}}>
      <Sfx
        cues={[
          {src: 'Suspense.mp3', atFrame: 6, volume: 0.4},
          {src: 'transitions.mp3', atFrame: SLASH, volume: 0.65},
        ]}
      />

      <Screentone color={PAPER} size={20} radius={2.2} opacity={0.1} drift={-0.2} />

      <AbsoluteFill style={{transform: `translateX(${shake}px)`}}>
        <div
          style={{
            position: 'absolute',
            top: 300,
            width: '100%',
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <CelText size={104} color={PAPER} outline={INK} shadow={PINK} style={{textAlign: 'center'}}>
            {'NOBODY TELLS\nYOU WHICH'}
          </CelText>
        </div>

        {/* Hollow cards: the tools nobody names. */}
        <div
          style={{
            position: 'absolute',
            top: 860,
            left: 0,
            display: 'flex',
            gap: 40,
            transform: `translateX(${drift}px)`,
          }}
        >
          {new Array(CARDS).fill(0).map((_, i) => {
            const cardTop = 860;
            const stamped = scanY > cardTop + 120 + i * 4;
            return (
              <div
                key={i}
                style={{
                  width: 300,
                  height: 380,
                  border: `8px dashed ${PAPER}`,
                  borderRadius: 22,
                  opacity: 0.55,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    fontFamily: LABEL,
                    fontSize: 150,
                    color: stamped ? PINK : 'transparent',
                    WebkitTextStroke: stamped ? 'none' : `5px ${PAPER}`,
                    transform: stamped ? 'scale(1)' : 'scale(0.85)',
                  }}
                >
                  ?
                </div>
              </div>
            );
          })}
        </div>

        {/* Scanline sweep */}
        {scanOn ? (
          <div
            style={{
              position: 'absolute',
              top: scanY,
              left: 0,
              width: '100%',
              height: 6,
              background: PINK,
              boxShadow: `0 0 60px 18px ${PINK}`,
            }}
          />
        ) : null}

        {/* Ink slash across the row */}
        <svg
          width={1080}
          height={1920}
          viewBox="0 0 1080 1920"
          style={{position: 'absolute', inset: 0}}
        >
          <line
            x1={-40}
            y1={1340}
            x2={-40 + 1180 * slash}
            y2={1340 - 420 * slash}
            stroke={PINK}
            strokeWidth={26}
            strokeLinecap="round"
          />
        </svg>

        <div
          style={{
            position: 'absolute',
            bottom: 250,
            width: '100%',
            textAlign: 'center',
            fontFamily: LABEL,
            fontSize: 58,
            letterSpacing: '0.18em',
            color: PAPER,
            opacity: interpolate(frame, [SLASH + 6, SLASH + 20], [0, 0.75], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            }),
          }}
        >
          ACTUALLY DO IT
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
