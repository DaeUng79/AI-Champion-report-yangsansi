import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

import type { HookProvider } from '../../../../../core/src/provider.js';
import {
  BASH_COMMAND_DISPLAY_MAX_LENGTH,
  TASK_DESCRIPTION_DISPLAY_MAX_LENGTH,
} from '../../../constants.js';
import { CODEX_TERMINAL_NAME_PREFIX, OPENROUTER_BASE_URL } from './constants.js';

function formatToolStatus(toolName: string, input?: unknown): string {
  const inp = (input ?? {}) as Record<string, unknown>;
  const base = (p: unknown) => (typeof p === 'string' ? path.basename(p) : '');
  switch (toolName) {
    case 'exec_command': {
      const cmd = (inp.cmd as string) || '';
      return `Running: ${cmd.length > BASH_COMMAND_DISPLAY_MAX_LENGTH ? cmd.slice(0, BASH_COMMAND_DISPLAY_MAX_LENGTH) + '\u2026' : cmd}`;
    }
    case 'write_stdin':
      return 'Streaming terminal output';
    case 'search_query':
      return 'Searching the web';
    case 'open':
      return 'Opening web page';
    case 'find':
      return 'Finding text';
    case 'apply_patch':
      return 'Editing files';
    case 'parallel':
      return 'Running tasks in parallel';
    case 'time':
      return 'Checking time';
    case 'weather':
      return 'Checking weather';
    case 'sports':
      return 'Checking sports data';
    case 'finance':
      return 'Checking market data';
    case 'read_file':
      return `Reading ${base(inp.path)}`;
    case 'write_file':
      return `Writing ${base(inp.path)}`;
    case 'task': {
      const desc = typeof inp.description === 'string' ? inp.description : '';
      return desc
        ? `Subtask: ${desc.length > TASK_DESCRIPTION_DISPLAY_MAX_LENGTH ? desc.slice(0, TASK_DESCRIPTION_DISPLAY_MAX_LENGTH) + '\u2026' : desc}`
        : 'Running subtask';
    }
    default:
      return `Using ${toolName}`;
  }
}

function datePathPart(value: number): string {
  return String(value).padStart(2, '0');
}

function getCodexSessionsRoot(): string {
  const fromEnv = process.env['PIXEL_AGENTS_CODEX_SESSIONS_ROOT']?.trim();
  if (fromEnv) return fromEnv;
  return path.join(os.homedir(), '.codex', 'sessions');
}

function findLatestSessionDayDir(root: string): string | null {
  try {
    const years = fs
      .readdirSync(root, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()
      .reverse();
    for (const year of years) {
      const yearDir = path.join(root, year);
      const months = fs
        .readdirSync(yearDir, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => entry.name)
        .sort()
        .reverse();
      for (const month of months) {
        const monthDir = path.join(yearDir, month);
        const days = fs
          .readdirSync(monthDir, { withFileTypes: true })
          .filter((entry) => entry.isDirectory())
          .map((entry) => entry.name)
          .sort()
          .reverse();
        for (const day of days) {
          const dayDir = path.join(monthDir, day);
          const hasJsonl = fs.readdirSync(dayDir).some((file) => file.endsWith('.jsonl'));
          if (hasJsonl) return dayDir;
        }
      }
    }
  } catch {
    return null;
  }
  return null;
}

function getSessionDirs(_workspacePath: string): string[] {
  const fixed = process.env['PIXEL_AGENTS_CODEX_SESSION_DIR']?.trim();
  if (fixed) return [fixed];

  const root = getCodexSessionsRoot();
  const now = new Date();
  const todayDir = path.join(
    root,
    String(now.getFullYear()),
    datePathPart(now.getMonth() + 1),
    datePathPart(now.getDate()),
  );
  if (fs.existsSync(todayDir)) return [todayDir];

  const latestDir = findLatestSessionDayDir(root);
  if (latestDir) return [latestDir];

  return [todayDir];
}

function getAllSessionRoots(): string[] {
  const root = getCodexSessionsRoot();
  const now = new Date();
  const monthDir = path.join(root, String(now.getFullYear()), datePathPart(now.getMonth() + 1));
  return [monthDir];
}

function buildLaunchEnv(cwd: string): Record<string, string> {
  const env: Record<string, string> = { PWD: cwd };

  const openrouterKey = process.env['OPENROUTER_API_KEY']?.trim();
  if (openrouterKey && !process.env['OPENAI_API_KEY']) {
    env.OPENAI_API_KEY = openrouterKey;
  }
  if (openrouterKey && !process.env['OPENAI_BASE_URL']) {
    env.OPENAI_BASE_URL = process.env['OPENROUTER_BASE_URL']?.trim() || OPENROUTER_BASE_URL;
  }
  const openrouterModel = process.env['OPENROUTER_MODEL']?.trim();
  if (openrouterModel && !process.env['OPENAI_MODEL']) {
    env.OPENAI_MODEL = openrouterModel;
  }
  return env;
}

function buildLaunchCommand(
  _sessionId: string,
  cwd: string,
  _opts?: { bypassPermissions?: boolean },
): { command: string; args: string[]; env?: Record<string, string> } {
  const command = process.env['PIXEL_AGENTS_CODEX_COMMAND']?.trim() || 'codex';
  return { command, args: [], env: buildLaunchEnv(cwd) };
}

function normalizeHookEvent(_raw: Record<string, unknown>) {
  return null;
}

function installHooks(_serverUrl: string, _authToken: string): Promise<void> {
  return Promise.resolve();
}

function uninstallHooks(): Promise<void> {
  return Promise.resolve();
}

function areHooksInstalled(): Promise<boolean> {
  return Promise.resolve(false);
}

export const codexProvider: HookProvider = {
  kind: 'hook',
  id: 'codex',
  displayName: 'Codex',
  supportsHooks: false,
  protocolVersion: 1,

  normalizeHookEvent,

  installHooks,
  uninstallHooks,
  areHooksInstalled,

  formatToolStatus,
  permissionExemptTools: new Set(['search_query', 'open', 'find', 'time', 'weather', 'sports']),
  subagentToolNames: new Set(),
  readingTools: new Set(['search_query', 'open', 'find', 'time', 'weather', 'sports', 'finance']),
  terminalNamePrefix: CODEX_TERMINAL_NAME_PREFIX,

  getSessionDirs,
  getAllSessionRoots,
  sessionFilePattern: '*.jsonl',
  buildLaunchCommand,
};
