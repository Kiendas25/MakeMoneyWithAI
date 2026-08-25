import type {FC} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {CelText, GOLD, INK, LABEL, MONO, PAPER, PINK, Screentone} from '../anime/kit';
import {Sfx} from '../anime/Sfx';

// Row data is taken straight from this repository's README.
const ROWS = [
  {rank: 1, name: 'AutoGPT', stars: '178.8k'},
  {rank: 2, name: 'stable-diffusion', stars: '157.0k'},
  {rank: 4, name: 'ollama', stars: '153.4k'},
  {rank: 5, name: 'transformers', stars: '150.5k'},
  {rank: 6, name: 'n8n', stars: '143.7k'},
  {rank: 8, name: 'langchain', stars: '116.5k'},
  {rank: 9, name: 'dify', stars: '115.6k'},
  {rank: 11, name: 'ComfyUI', stars: '89.8k'},
];

const ROW_H = 150;
const VIEW_TOP = 680;
const VIEW_H = 900;
const FOCUS_LOCAL = 450; // centre of the viewport
const SCROLL_FROM = -300;
const SCROLL_TO = 675;
const LOCK = 132;

export const StarRankedScroll: FC = () => {
  const frame = useCurrentFrame();

  const scroll = interpolate(frame, [0, LOCK], [SCROLL_FROM, SCROLL_TO], {
    extrapolateRight: 'clamp',
  });
  const counter = Math.round(
    interpolate(frame, [8, LOCK], [0, 500], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: (v) => 1 - Math.pow(1 - v, 2.2),
    })
  );
  const punch = interpolate(frame, [LOCK, LOCK + 12], [1, 1.07], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });

  return (
    <AbsoluteFill style={{background: PAPER, overflow: 'hidden'}}>
      <Sfx
        cues={[
          {src: 'Pop.mp3', atFrame: 10},
          {src: 'Pop.mp3', atFrame: 30},
          {src: 'Pop.mp3', atFrame: 51},
          {src: 'Pop.mp3', atFrame: 71},
          {src: 'Pop.mp3', atFrame: 91},
          {src: 'Pop.mp3', atFrame: 112},
          {src: 'Correct.mp3', atFrame: LOCK, volume: 0.65},
        ]}
      />

      <Screentone color={INK} size={13} radius={2.4} opacity={0.12} />
      <AbsoluteFill
        style={{background: `linear-gradient(180deg, ${GOLD}44 0%, transparent 40%, ${PINK}2e 100%)`}}
      />

      <AbsoluteFill style={{transform: `scale(${punch})`}}>
        {/* Scroll viewport — clipped so rows never reach the header or footer. */}
        <div
          style={{
            position: 'absolute',
            top: VIEW_TOP,
            left: 0,
            width: '100%',
            height: VIEW_H,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: FOCUS_LOCAL - ROW_H / 2,
              left: 0,
              width: '100%',
              height: ROW_H,
              background: `${GOLD}55`,
              borderTop: `5px solid ${INK}`,
              borderBottom: `5px solid ${INK}`,
            }}
          />

          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 70,
              right: 70,
              transform: `translateY(${-scroll}px)`,
            }}
          >
            {ROWS.map((row, i) => {
              const centre = i * ROW_H + ROW_H / 2 - scroll;
              const dist = Math.abs(centre - FOCUS_LOCAL);
              const focused = dist < ROW_H / 2;
              const burst = focused ? interpolate(dist, [0, ROW_H / 2], [1, 0]) : 0;
              return (
                <div
                  key={row.name}
                  style={{
                    height: ROW_H,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 26,
                    opacity: focused ? 1 : 0.38,
                    transform: `scale(${focused ? 1.03 : 0.97})`,
                    transformOrigin: 'left center',
                  }}
                >
                  <div style={{fontFamily: LABEL, fontSize: 56, color: INK, width: 100, opacity: 0.5}}>
                    {String(row.rank).padStart(2, '0')}
                  </div>
                  <div
                    style={{
                      fontFamily: MONO,
                      fontWeight: 700,
                      fontSize: row.name.length > 13 ? 50 : 62,
                      color: INK,
                      flex: 1,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.name}
                  </div>
                  <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
                    <svg width={64} height={64} viewBox="0 0 24 24">
                      <path
                        d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.3 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8z"
                        fill={focused ? GOLD : 'none'}
                        stroke={INK}
                        strokeWidth={1.8}
                        strokeLinejoin="round"
                        style={{transformOrigin: 'center', transform: `scale(${1 + burst * 0.3})`}}
                      />
                    </svg>
                    <div style={{fontFamily: LABEL, fontSize: 54, color: INK}}>{row.stars}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Header band sits above the viewport on solid stock. */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: VIEW_TOP,
            background: PAPER,
            borderBottom: `8px solid ${INK}`,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Screentone color={INK} size={13} radius={2.4} opacity={0.1} />
          <div style={{width: '100%'}}>
            <CelText size={200} color={GOLD} outline={INK} shadow={PINK} strokeWidth={14} align="center">
              {`${counter}+`}
            </CelText>
          </div>
          <div
            style={{
              fontFamily: LABEL,
              fontSize: 50,
              letterSpacing: '0.18em',
              color: INK,
              marginTop: 40,
              textAlign: 'center',
            }}
          >
            OPEN-SOURCE AI PROJECTS
          </div>
        </div>

        {/* Footer band */}
        <div
          style={{
            position: 'absolute',
            top: VIEW_TOP + VIEW_H,
            left: 0,
            width: '100%',
            bottom: 0,
            background: PAPER,
            borderTop: `8px solid ${INK}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Screentone color={INK} size={13} radius={2.4} opacity={0.1} />
          <div
            style={{
              fontFamily: LABEL,
              fontSize: 62,
              letterSpacing: '0.2em',
              color: INK,
              position: 'relative',
            }}
          >
            RANKED BY STARS
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
