/**
 * Provider registry: re-exports all bundled providers.
 *
 * Adding a new CLI provider:
 *   1. Create `server/src/providers/hook/<cli>/<cli>.ts` implementing HookProvider.
 *      (File-based and stream-based provider types will land when the first such
 *       provider ships.)
 *   2. Add an export line below.
 *
 * The adapter (VS Code extension, standalone CLI, etc.) imports from here rather
 * than reaching into each provider directory directly.
 */

import type { HookProvider } from '../../../core/src/provider.js';
import { claudeProvider } from './hook/claude/claude.js';
import { copyHookScript as copyClaudeHookScript } from './hook/claude/claudeHookInstaller.js';
import { codexProvider } from './hook/codex/codex.js';

const PROVIDERS = {
  claude: claudeProvider,
  codex: codexProvider,
} as const;

export type ProviderId = keyof typeof PROVIDERS;

export { claudeProvider, codexProvider };

/** Return the active provider from PIXEL_AGENTS_PROVIDER. Defaults to Claude. */
export function getActiveProvider(env: NodeJS.ProcessEnv = process.env): HookProvider {
  const requested = env['PIXEL_AGENTS_PROVIDER']?.trim().toLowerCase() ?? '';
  if (!requested) return claudeProvider;
  const provider = PROVIDERS[requested as ProviderId];
  if (provider) return provider;
  console.warn(
    `[Pixel Agents] Unknown PIXEL_AGENTS_PROVIDER="${requested}". Falling back to "${claudeProvider.id}".`,
  );
  return claudeProvider;
}

/** True when this provider has working hook install/uninstall support. */
export function providerSupportsHooks(provider: HookProvider): boolean {
  return provider.supportsHooks !== false;
}

/** Normalize the hooks toggle for providers without hook support. */
export function normalizeHooksEnabled(provider: HookProvider, requested: boolean): boolean {
  return providerSupportsHooks(provider) ? requested : false;
}

/** Copy the hook script if the active provider ships one. No-op otherwise. */
export function copyHookScript(
  extensionPath: string,
  provider: HookProvider = getActiveProvider(),
): void {
  if (provider.id === 'claude') {
    copyClaudeHookScript(extensionPath);
  }
}
