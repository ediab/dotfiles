/**
 * opencode-jev-key-sync — makes TypeSafe's Jev classifier models work with the
 * rotated OpenCode key pool.
 *
 * The built-in `opencode` provider serves the Jev classifiers
 * (jev-1.13, jev-1.13-free) at https://opencode.ai/zen/v1/systemone, but
 * authenticates only via OPENCODE_API_KEY / auth.json["opencode"] — a channel
 * the @lnilluv/pi-opencode-go-rotation extension never fills (it injects keys
 * into its own `opencode-go` provider only).
 *
 * This extension resolves whatever key the rotation extension currently has
 * active (`getApiKeyForProvider("opencode-go")` follows the runtime override,
 * auth.json fallback, and any mid-session rotation) and applies it to the
 * built-in `opencode` provider's runtime key store. Synced at session start
 * and before each agent run, so rotation drift is caught at the next prompt.
 */

const ROTATED_PROVIDER = "opencode-go";
const TARGET_PROVIDER = "opencode";

function getRuntimeKeyStore(modelRegistry: any) {
	const store = modelRegistry.authStorage ?? modelRegistry.runtime;
	if (!store) throw new Error("Model registry does not expose runtime API key storage");
	return store;
}

export default function () {
	return function opencodeJevKeySync(pi: any) {
		const appliedKeys = new WeakMap();

		async function sync(ctx: any): Promise<void> {
			try {
				const key = await ctx.modelRegistry.getApiKeyForProvider(ROTATED_PROVIDER);
				if (!key) return;
				if (appliedKeys.get(ctx.modelRegistry) === key) return;
				appliedKeys.set(ctx.modelRegistry, key);
				await getRuntimeKeyStore(ctx.modelRegistry).setRuntimeApiKey(TARGET_PROVIDER, key);
			} catch {
				// Fail open: classifier calls surface their own auth errors, and a
				// missing key here should never block the session.
			}
		}

		pi.on("session_start", async (_event: unknown, ctx: any) => {
			appliedKeys.delete(ctx.modelRegistry); // re-apply after /reload or resume
			await sync(ctx);
		});

		pi.on("before_agent_start", async (_event: unknown, ctx: any) => {
			await sync(ctx);
		});
	};
}
