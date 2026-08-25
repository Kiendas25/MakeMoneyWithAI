import type {FC} from 'react';
import {Composition} from 'remotion';
import './anime/fonts';
import {EmptyToolbox} from './scenes/EmptyToolbox';
import {MonetizeAnnotation} from './scenes/MonetizeAnnotation';
import {PickOneShipIt} from './scenes/PickOneShipIt';
import {PromiseFlash} from './scenes/PromiseFlash';
import {RapidFireCards} from './scenes/RapidFireCards';
import {StarRankedScroll} from './scenes/StarRankedScroll';

const V = {width: 1080, height: 1920, fps: 30} as const;

// One independent Composition per approved scene, per flick-plan.md.
// There is deliberately no all-scenes composition.
export const RemotionRoot: FC = () => (
  <>
    <Composition id="promise-flash" component={PromiseFlash} durationInFrames={120} {...V} />
    <Composition id="empty-toolbox" component={EmptyToolbox} durationInFrames={135} {...V} />
    <Composition id="star-ranked-scroll" component={StarRankedScroll} durationInFrames={165} {...V} />
    <Composition id="rapid-fire-cards" component={RapidFireCards} durationInFrames={165} {...V} />
    <Composition id="monetize-annotation" component={MonetizeAnnotation} durationInFrames={150} {...V} />
    <Composition id="pick-one-ship-it" component={PickOneShipIt} durationInFrames={150} {...V} />
  </>
);
