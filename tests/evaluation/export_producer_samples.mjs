// Exercise the real CSV, support-declaration, event, manifest and TAR exporters.
// Inputs are artificial sanitized fixtures; this never connects to a runtime.
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const [producer, output] = process.argv.slice(2);
if (!producer || !output || process.argv.length !== 4) {
  throw new Error('usage: node --experimental-strip-types export_producer_samples.mjs PRODUCER OUTPUT');
}
const feature = path.resolve(producer, 'apps/web/src/features/player/research');
const { createResearchRunExportArtifacts } = await import(pathToFileURL(path.join(feature, 'researchRunExportArtifacts.ts')));
const { createResearchRunBundleTar } = await import(pathToFileURL(path.join(feature, 'researchRunBundle.ts')));
const fixture = fileURLToPath(new URL('../data/pixelated_bundle/valid-v2/', import.meta.url));
const read = name => readFile(path.join(fixture, name), 'utf8');
const original = JSON.parse(await read('bundle-manifest.json'));

// This is a decoder only for these pinned, unquoted test CSVs, not a general
// importer. Keep strings explicit so numeric-looking IDs cannot change type.
async function samples(name, stringFields) {
  const text = await read(name);
  if (text.includes('"') || text.length > 65536) throw new Error('unexpected test CSV');
  const [header, ...rows] = text.trimEnd().split(/\r?\n/).map(row => row.split(','));
  return rows.map(row => {
    if (row.length !== header.length) throw new Error('incomplete test CSV');
    return Object.fromEntries(header.map((field, i) => {
      const key = field.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
      const raw = row[i];
      const value = raw === '' ? null : stringFields.has(key) ? raw
        : raw === 'true' ? true : raw === 'false' ? false : Number(raw);
      if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('bad test value');
      return [key, value];
    }));
  });
}
const browser = await samples('stream-telemetry.csv', new Set([
  'capturedAt', 'sessionId', 'gameId', 'playerMode', 'status',
  'iceConnectionState', 'connectionState', 'lastEngineError',
]));
const engine = await samples('engine-telemetry.csv', new Set([
  'capturedAt', 'runId', 'sessionId', 'gameId', 'source', 'error', 'runtimeKind',
]));
const events = (await samples('stream-events.csv', new Set([
  'capturedAt', 'runId', 'sessionId', 'event', 'detailsJson',
]))).map(({ event, detailsJson, ...row }) => ({
  ...row, name: event, details: detailsJson === null ? null : JSON.parse(detailsJson),
}));
const date = new Date(original.createdAt);
const files = createResearchRunExportArtifacts({
  comparisonCaseId: original.comparisonCaseId, engineSamples: engine, events,
  graphPng: null, metadataJson: await read('run-metadata.json'), phase: original.phase,
  recordedAt: date, runId: original.runId, samples: browser,
  summaryJson: await read('summary.json'),
});
await writeFile(output, createResearchRunBundleTar(files, date), { flag: 'wx', mode: 0o600 });
