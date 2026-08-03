#!/usr/bin/env node

import { cp, mkdir, readdir, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE = path.join(PACKAGE_ROOT, "skill", "adaptive-learning-coach");
const COMMAND_SOURCE = path.join(PACKAGE_ROOT, "commands", "learn.md");

function printHelp() {
  console.log(`Usage:
  studyany-adaptive-learning-coach install [options]

Scopes:
  --scope project     install in the current project (default for npm dependency install)
  --scope global      install for the current user (default for npm -g install)

Options:
  --client <names>    claude, cursor, codex, or a comma-separated list
  --dry-run           show targets without copying files
  --help              show this help

Examples:
  npm install -g studyany-adaptive-learning-coach@latest
  npx studyany-adaptive-learning-coach install --scope global --client claude,codex
  npx studyany-adaptive-learning-coach install --scope project --client claude,cursor
  npx studyany-adaptive-learning-coach install --scope global --dry-run`);
}

function defaultScope() {
  return process.env.npm_config_global === "true" ? "global" : "project";
}

function defaultClients(scope) {
  return scope === "global" ? ["claude", "codex"] : ["claude", "cursor"];
}

function parseArgs(argv) {
  const options = {
    auto: false,
    clients: null,
    dryRun: false,
    help: false,
    scope: defaultScope()
  };

  let index = 0;
  if (argv[0] === "install") index += 1;
  while (index < argv.length) {
    const arg = argv[index];
    if (arg === "--auto") {
      options.auto = true;
    } else if (arg === "--dry-run") {
      options.dryRun = true;
    } else if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--scope") {
      const value = argv[index + 1];
      if (!value) throw new Error("--scope requires project or global");
      options.scope = value;
      index += 1;
    } else if (arg === "--client") {
      const value = argv[index + 1];
      if (!value) throw new Error("--client requires claude, cursor, codex, or a list");
      options.clients = value.split(",").map((name) => name.trim()).filter(Boolean);
      index += 1;
    } else {
      throw new Error(`unknown option: ${arg}`);
    }
    index += 1;
  }

  if (!new Set(["project", "global"]).has(options.scope)) {
    throw new Error(`unknown scope: ${options.scope}`);
  }
  options.clients = options.clients || defaultClients(options.scope);
  const supported = options.scope === "global" ? ["claude", "codex"] : ["claude", "cursor"];
  const invalid = options.clients.filter((client) => !supported.includes(client));
  if (invalid.length > 0) {
    throw new Error(
      `unsupported client(s) for ${options.scope} scope: ${invalid.join(", ")}. ` +
      `Supported clients: ${supported.join(", ")}`
    );
  }
  return options;
}

async function ensureSourceExists() {
  const sourceStats = await stat(SOURCE);
  if (!sourceStats.isDirectory()) throw new Error(`skill source is not a directory: ${SOURCE}`);
  const commandStats = await stat(COMMAND_SOURCE);
  if (!commandStats.isFile()) throw new Error(`Claude command source is missing: ${COMMAND_SOURCE}`);
}

async function listFiles(directory, prefix = "") {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const relative = path.join(prefix, entry.name);
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await listFiles(fullPath, relative)));
    } else {
      files.push(relative);
    }
  }
  return files;
}

function globalRoots() {
  const home = os.homedir();
  const codexHome = process.env.CODEX_HOME || path.join(home, ".codex");
  return {
    claude: path.join(home, ".claude"),
    codex: codexHome
  };
}

function projectRoots() {
  return {
    claude: path.resolve(process.env.INIT_CWD || process.cwd()),
    cursor: path.resolve(process.env.INIT_CWD || process.cwd())
  };
}

function targetFor(scope, client) {
  const root = scope === "global" ? globalRoots()[client] : projectRoots()[client];
  const skillDirectory = scope === "global" || client === "codex"
    ? path.join(root, "skills", "adaptive-learning-coach")
    : path.join(root, `.${client}`, "skills", "adaptive-learning-coach");
  const commandDirectory = client === "claude"
    ? scope === "global"
      ? path.join(root, "commands")
      : path.join(root, ".claude", "commands")
    : null;
  return { root, skillDirectory, commandPath: commandDirectory ? path.join(commandDirectory, "learn.md") : null };
}

function assertInsideRoot(root, destination) {
  const relative = path.relative(path.resolve(root), path.resolve(destination));
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`refusing to write outside selected root: ${destination}`);
  }
}

async function install(options) {
  await ensureSourceExists();
  const files = await listFiles(SOURCE);
  for (const client of options.clients) {
    const target = targetFor(options.scope, client);
    assertInsideRoot(target.root, target.skillDirectory);
    if (target.commandPath) assertInsideRoot(target.root, target.commandPath);
    const verb = options.dryRun ? "Would install" : "Installing";
    console.log(`${verb} ${client} skill: ${target.skillDirectory}`);
    if (options.dryRun) {
      for (const file of files) console.log(`  ${path.join(target.skillDirectory, file)}`);
      if (target.commandPath) console.log(`  ${target.commandPath}`);
      continue;
    }
    await mkdir(target.skillDirectory, { recursive: true });
    await cp(SOURCE, target.skillDirectory, { recursive: true, force: true });
    if (target.commandPath) {
      await mkdir(path.dirname(target.commandPath), { recursive: true });
      await cp(COMMAND_SOURCE, target.commandPath, { force: true });
      console.log(`Installing Claude command: ${target.commandPath}`);
    }
  }
  if (!options.dryRun) console.log(`${options.scope} skill installation complete.`);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }
  if (options.auto && process.env.STUDYANY_SKIP_INSTALL === "1") {
    console.log("Automatic skill installation skipped by STUDYANY_SKIP_INSTALL=1.");
    return;
  }
  await install(options);
}

const auto = process.argv.includes("--auto");
try {
  await main();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  if (auto) {
    console.warn(`Automatic skill installation was not completed: ${message}`);
    console.warn("Run the package command explicitly after installation: npx studyany-adaptive-learning-coach install --scope global");
  } else {
    console.error(`Skill installation failed: ${message}`);
    process.exitCode = 1;
  }
}
