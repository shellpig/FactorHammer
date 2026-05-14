import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const source = resolve(__dirname, "../../docs/mock_dashboard_payload.json");
const target = resolve(__dirname, "../public/mock/dashboard_2330.json");

mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);
console.log(`Synced dashboard mock: ${source} -> ${target}`);
