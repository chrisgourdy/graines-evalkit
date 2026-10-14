// Generates src/contracts/<Name>.ts from ../../schemas/*.schema.json (output of
// `evalkit export-schemas`) plus src/contracts/index.ts re-exporting the top-level types.
// Single source of truth: the Python contracts. Run `npm run gen` after any contract change.
import { compile } from "json-schema-to-typescript";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const schemasDir = path.resolve(process.cwd(), "../../schemas");
const outDir = path.resolve(process.cwd(), "src/contracts");
await mkdir(outDir, { recursive: true });
const files = (await readdir(schemasDir)).filter((f) => f.endsWith(".schema.json")).sort();
const names = [];
for (const f of files) {
  const schema = JSON.parse(await readFile(path.join(schemasDir, f), "utf8"));
  const name = f.replace(".schema.json", "");
  const ts = await compile(schema, name, {
    bannerComment: `/* eslint-disable */\n// GENERATED from schemas/${f} by scripts/gen-types.mjs — do not edit.`,
    additionalProperties: false,
  });
  await writeFile(path.join(outDir, `${name}.ts`), ts);
  names.push(name);
}
const index = names.map((n) => `export type { ${n} } from "./${n}.js";`).join("\n") + "\n";
await writeFile(path.join(outDir, "index.ts"), `// GENERATED — top-level contract types.\n${index}`);
console.log(`generated ${names.length} contract modules: ${names.join(", ")}`);
