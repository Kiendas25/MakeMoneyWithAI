import type {FC} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {
  CelText,
  GOLD,
  INK,
  ImpactFlash,
  LABEL,
  PAPER,
  Petals,
  PINK,
  Screentone,
  SpeedLines,
  Sunburst,
  slamIn,
} from '../anime/kit';
import {Sfx} from '../anime/Sfx';

const WORDS = [
  {text: 'STAR IT', at: 22, seed: 5},
  {text: 'PICK ONE', at: 48, seed: 13},
  {text: 'SHIP IT', at: 74, seed: 29},
];
const MARK = 110;

export const PickOneShipIt: FC = () => {
  const frame = useCurrentFrame();

  // The hollow star fills gold and bursts — the emotional beat before the CTA.
  const fill = interpolate(frame, [8, 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const starPop = interpolate(frame, [18, 26], [1, 1.3], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });
  const starFade = interpolate(frame, [30, 46], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const mark = slamIn(frame, MARK, {overshoot: 1.22, settle: 12});
  const markRule = interpolate(frame, [MARK + 8, MARK + 22], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });
  const active = WORDS.filter((w) => frame >= w.at && frame < MARK);

  return (
    <AbsoluteFill style={{background: INK, overflow: 'hidden'}}>
      <Sfx
        cues={[
          {src: 'aha-moment.MP3', atFrame: 12, volume: 0.55},
          {src: 'energy.MP3', atFrame: MARK, volume: 0.6},
        ]}
      />

      <Sunburst color={GOLD} wedges={24} speed={-0.2} opacity={0.16} />
      <Screentone color={GOLD} size={18} radius={3} opacity={0.12} drift={0.3} />
      <Petals count={30} seed={41} color={PINK} opacity={0.5} />

      {active.map((w) => (
        <SpeedLines
          key={w.text}
          count={70}
          color={GOLD}
          seed={w.seed}
          progress={interpolate(frame, [w.at, w.at + 10], [0.2, 1], {extrapolateRight: 'clamp'})}
          inner={320}
          opacity={0.28}
        />
      ))}

      {/* Star fill */}
      {starFade > 0 ? (
        <AbsoluteFill
          style={{alignItems: 'center', justifyContent: 'center', opacity: starFade}}
        >
          <svg width={420} height={420} viewBox="0 0 24 24" style={{transform: `scale(${starPop})`}}>
            <defs>
              <linearGradient id="starfill" x1="0" y1="1" x2="0" y2="0">
                <stop offset={fill} stopColor={GOLD} />
                <stop offset={fill} stopColor="transparent" />
              </linearGradient>
            </defs>
            <path
              d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17.3 5.9 20.6l1.4-6.8L2.2 9.1l6.9-.8z"
              fill="url(#starfill)"
              stroke={PAPER}
              strokeWidth={1.2}
              strokeLinejoin="round"
            />
          </svg>
        </AbsoluteFill>
      ) : null}

      {/* Three word slams, stacked */}
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 40}}>
        {WORDS.map((w, i) => {
          if (frame < w.at || frame >= MARK) return null;
          const s = slamIn(frame, w.at, {overshoot: 1.3, settle: 12});
          return (
            <div
              key={w.text}
              style={{
                transform: `scale(${s.scale}) rotate(${i % 2 === 0 ? -2.5 : 2.5}deg)`,
                opacity: s.opacity,
              }}
            >
              <CelText
                size={152}
                color={i === 2 ? GOLD : PAPER}
                outline={INK}
                shadow={PINK}
                strokeWidth={14}
              >
                {w.text}
              </CelText>
            </div>
          );
        })}
      </AbsoluteFill>

      {/* Final wordmark */}
      {frame >= MARK ? (
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
          <div style={{transform: `scale(${mark.scale})`, opacity: mark.opacity, width: 900}}>
            <CelText size={96} color={PAPER} outline={INK} shadow={PINK} strokeWidth={11} align="center">
              {'MAKE MONEY\nWITH AI'}
            </CelText>
          </div>
          <div
            style={{
              marginTop: 130,
              width: `${markRule * 620}px`,
              height: 16,
              background: GOLD,
              border: `5px solid ${INK}`,
              borderRadius: 8,
            }}
          />
          <div
            style={{
              marginTop: 40,
              fontFamily: LABEL,
              fontSize: 42,
              letterSpacing: '0.24em',
              color: PAPER,
              opacity: markRule * 0.8,
            }}
          >
            500+ PROJECTS · RANKED
          </div>
        </AbsoluteFill>
      ) : null}

      {WORDS.map((w) => (
        <ImpactFlash key={w.text} at={w.at} duration={3} color="#fff" />
      ))}
      <ImpactFlash at={MARK} duration={5} color={GOLD} />
    </AbsoluteFill>
  );
};
