/** BB owns automatic titles; pstack supplies Pi's question tool. */
import { join } from "node:path";
import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default async function standaloneUI(pi: ExtensionAPI): Promise<void> {
	if (process.env.BB_THREAD_ID) return;

	// Normal autoload is disabled by extensions: [] in settings.json.
	const { default: register } = await import(
		join(getAgentDir(), "npm", "node_modules", "pi-title", "index.ts")
	);
	await register(pi);
}
