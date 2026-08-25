import type {FC} from 'react';
import {Audio, Sequence, staticFile} from 'remotion';

export type Cue = {src: string; atFrame: number; volume?: number};

/** Bundled action-matched sound effects. One Sequence per cue. */
export const Sfx: FC<{cues: Cue[]}> = ({cues}) => (
  <>
    {cues.map((cue, i) => (
      <Sequence key={`${cue.src}-${cue.atFrame}-${i}`} from={cue.atFrame}>
        <Audio src={staticFile(`sounds/${cue.src}`)} volume={cue.volume ?? 0.55} />
      </Sequence>
    ))}
  </>
);
