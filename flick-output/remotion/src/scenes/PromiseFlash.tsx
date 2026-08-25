import type {FC} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {
  CelText,
  GOLD,
  INK,
  ImpactFlash,
  LABEL,
  PAPER,
  PINK,
  Screentone,
  SpeedLines,
  Sunburst,
  slamIn,
} from '../anime/kit';
import {Sfx} from '../anime/Sfx';

const SLAM = 18;

export const PromiseFlash: FC = () => {
  const frame = useCurrentFrame();

  // Speed lines rush outward on the slam, then hold wide.
  const rush = interpolate(frame, [SLAM - 6, SLAM + 6], [0.15, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const rich = slamIn(frame, SLAM, {overshoot: 1.34, settle: 16});
  const split = interpolate(frame, [SLAM, SLAM + 5], [26, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const kicker = interpolate(frame, [4, 14], [0, 1], {extrapolateRight: 'clamp'});
  const kickerY = interpolate(frame, [4, 14], [40, 0], {
    extrapolateRight: 'clamp',
    easing: (v) => 1 - Math.pow(1 - v, 3),
  });
  // Slow push-in keeps the frame alive after the slam settles.
  const push = interpolate(frame, [SLAM, 120], [1, 1.06], {extrapolateLeft: 'clamp'});

  return (
    <AbsoluteFill style={{background: INK, overflow: 'hidden'}}>
      <Sfx cues={[{src: 'Impact.mp3', atFrame: SLAM, volume: 0.7}]} />

      <AbsoluteFill style={{transform: `scale(${push})`}}>
        <Sunburst color={GOLD} wedges={20} speed={0.18} opacity={0.22} />
        <Screentone color={GOLD} size={16} radius={3} opacity={0.14} drift={0.35} />
        <SpeedLines count={110} color={GOLD} seed={11} progress={rush} inner={300} opacity={0.5} />

        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column'}}>
          <div
            style={{
              opacity: kicker,
              transform: `translateY(${kickerY}px)`,
              fontFamily: LABEL,
              fontSize: 62,
              letterSpacing: '0.22em',
              color: PAPER,
              textTransform: 'uppercase',
              marginBottom: 34,
            }}
          >
            Everyone says
          </div>

          <CelText size={128} color={PAPER} outline={INK} shadow={PINK} align="center" style={{marginBottom: 18}}>
            {'AI WILL\nMAKE YOU'}
          </CelText>

          <div
            style={{
              transform: `scale(${rich.scale}) rotate(-3deg)`,
              opacity: rich.opacity,
              marginTop: 104,
            }}
          >
            <CelText size={300} color={GOLD} outline={INK} shadow={PINK} split={split} strokeWidth={20} align="center">
              RICH
            </CelText>
          </div>
        </AbsoluteFill>
      </AbsoluteFill>

      <ImpactFlash at={SLAM} duration={5} color="#fff" />
      <ImpactFlash at={116} duration={4} color="#fff" />
    </AbsoluteFill>
  );
};
