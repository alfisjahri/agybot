// AgyBot — DS-Bot-style avatar renderer (Phase 8).
//
// Membungkus aset karakter DS-Bot (static/ds/characters.js + inks.js,
// DeepSeek Harness plugin, Apache 2.0 — lihat header di file-file itu)
// dalam API kecil yang dipakai halaman AgyBot (app.js, sidebar.js).
// ES module — halaman memuatnya lewat <script type="module">.
//
// Rendering = markup DS-Bot yang sama persis: body + shade + light +
// mata sebagai lubang mask (mata = latar belakang yang tembus pandang),
// jadi karakternya tampak seperti blob 3D lucu ala DS-Bot. Tiap instance
// memakai id mask unik (bt-mark-<n>) supaya banyak avatar di satu
// halaman tidak saling menimpa.
import {
  characterMarkup, shapeOf, shapeId, MASK_ID, nextMarkSerial,
  CHARACTER_COLORS, PICKER_SHAPES, PICKER_COLUMNS, SHAPES,
  maskBox, holes, bodyOf,
} from './ds/characters.js';
import { INKS, GRADIENTS, inkFill, paintCss } from './ds/inks.js';

export { CHARACTER_COLORS, PICKER_SHAPES, PICKER_COLUMNS, SHAPES, paintCss, inkFill };

// Urutan picker DS-Bot: PICKER_SHAPES dulu, lalu sisa bentuk.
export const ALL_SHAPES = [
  ...PICKER_SHAPES,
  ...Object.keys(SHAPES).filter(id => !PICKER_SHAPES.includes(id)),
];

// Warna dalam tema gelap AgyBot memakai nilai gelap INKS[*][1]
// (lihat --bt-ink-<nama> di style.css). Hex custom diteruskan apa adanya.
export function inkHex(color) {
  if (typeof color === 'string' && /^#[0-9a-f]{6}$/i.test(color)) return color;
  const pair = INKS[color];
  return pair ? pair[1] : INKS.gray[1];
}

let ringSerial = 0;

// Satu avatar karakter DS-Bot sebagai HTML.
// shape: id bentuk DS-Bot ("whale", "star", ...), color: nama warna
// DS-Bot ("blue", "aurora", ...) atau hex custom ("#2FA08C").
// size: px. state: "idle" | "thinking" | "working" (animasi di CSS).
export function dsAvatarHTML(shape, color, size = 36, state = 'idle') {
  const def = shapeOf(shape);
  const box = def.size;
  const mask = `bt-mark-${nextMarkSerial()}`;
  const markup = characterMarkup(shape, color).replaceAll(MASK_ID, mask);
  return `<span class="bt-mark" data-shape="${shapeId(shape)}" data-state="${state}" data-live style="width:${size}px;height:${size}px"><svg viewBox="0 0 ${box} ${box}" aria-hidden="true">${markup}</svg></span>`;
}

// Ring seleksi picker: garis mengikuti kontur bentuk (ala DS-Bot
// ShapeRing di bot-settings.js). Dipakai di atas avatar grid.
export function dsShapeRing(shape, size = 36) {
  const def = shapeOf(shape);
  const unit = def.size / size;
  const mask = `bt-ring-${++ringSerial}`;
  const markup = `<defs><mask id="${mask}" ${maskBox(def.size)}>${holes(def, `<g stroke="#000" stroke-width="${6 * unit}" stroke-linejoin="round">${bodyOf(def, '#000', true)}</g>`)}</mask></defs><g mask="url(#${mask})" stroke="currentColor" stroke-width="${8 * unit}" stroke-linejoin="round">${bodyOf(def, 'currentColor', true)}</g>`;
  return `<svg class="bt-ring" viewBox="0 0 ${def.size} ${def.size}" aria-hidden="true">${markup}</svg>`;
}

// Gradasi aurora untuk swatch warna (bukan untuk badan karakter —
// badan aurora di DS-Bot memakai --bt-ink-aurora, lihat inks.js).
export function auroraCss() {
  return paintCss('aurora');
}
export { GRADIENTS };
