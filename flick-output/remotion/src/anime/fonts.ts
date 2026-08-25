import {continueRender, delayRender, staticFile} from 'remotion';

// Fonts must be resolved before the first frame is captured, otherwise the
// headless renderer falls back mid-render and the type jumps between frames.
const handle = delayRender('load-display-fonts');

const faces: [string, string][] = [
  ['Anton', 'fonts/Anton.ttf'],
  ['ArchivoBlack', 'fonts/ArchivoBlack.ttf'],
];

Promise.all(
  faces.map(async ([family, file]) => {
    const face = new FontFace(family, `url(${staticFile(file)})`);
    await face.load();
    document.fonts.add(face);
  })
)
  .then(() => continueRender(handle))
  .catch(() => continueRender(handle));
