/** These packages stay installed, but BB owns questions and automatic titles. */
import { join } from "node:path";
import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default async function standaloneUI(pi: ExtensionAPI): Promise<void> {
	if (process.env.BB_THREAD_ID) return;

	// Their normal autoload is disabled by extensions: [] in settings.json.
	for (const name of ["@juicesharp/rpiv-ask-user-question", "pi-title"]) {
		const { default: register } = await import(
			join(getAgentDir(), "npm", "node_modules", name, "index.ts")
		);
		await register(pi);
	}
}
