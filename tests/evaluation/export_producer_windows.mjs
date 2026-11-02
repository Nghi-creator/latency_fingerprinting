// Offline interoperability: real producer composer/TAR writer, artificial telemetry.
// No engine, browser, network, runtime action, or empirical label is involved.
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const [producer, output] = process.argv.slice(2);
if (!producer || !output || process.argv.length !== 4) {
  throw new Error('usage: node --experimental-strip-types export_producer_windows.mjs PRODUCER OUTPUT');
}
const feature = path.resolve(producer, 'apps/web/src/features/player/research');
const { createResearchBundleV2Files } = await import(pathToFileURL(path.join(feature, 'researchBundleV2.ts')));
const { createResearchRunBundleTar } = await import(pathToFileURL(path.join(feature, 'researchRunBundle.ts')));
const fixture = fileURLToPath(new URL('../data/pixelated_bundle/valid-v2/', import.meta.url));
const original = JSON.parse(await readFile(path.join(fixture, 'bundle-manifest.json'), 'utf8'));
const contentFiles = await Promise.all(original.files.filter(f => f.name !== 'bundle-manifest.json').map(async f => ({
  name: f.name, data: await readFile(path.join(fixture, f.name), 'utf8'),
})));
const date = new Date(original.createdAt);
const files = createResearchBundleV2Files({
  comparisonCaseId: original.comparisonCaseId, contentFiles, createdAt: date,
  measurementSupport: original.measurementSupport, phase: original.phase,
  runId: original.runId, telemetrySources: original.telemetrySources,
});
await writeFile(output, createResearchRunBundleTar(files, date), { flag: 'wx', mode: 0o600 });
