# StudyAny Adaptive Learning Coach

This package distributes the `adaptive-learning-coach` skill for Claude and
Codex, with project-level Cursor support. It provides domain-agnostic tutoring,
active practice, spaced review, progress tracking, and a local study clock.

## Global Install

After publishing the package under an npm scope you own, users can install it
like a global CLI-managed skill package:

```text
npm install -g @your-scope/adaptive-learning-coach@latest
```

The global postinstall hook copies the skill to:

```text
~/.claude/skills/adaptive-learning-coach/
$CODEX_HOME/skills/adaptive-learning-coach/
```

When `CODEX_HOME` is not set, the Codex target defaults to `~/.codex/skills`.
Claude also receives the personal `/learn` command at `~/.claude/commands/learn.md`.

The explicit equivalent is:

```text
npx @your-scope/adaptive-learning-coach install --scope global --client claude,codex
```

Upgrade with the same global command:

```text
npm install -g @your-scope/adaptive-learning-coach@latest
```

The package name in `package.json` must be changed from the local development
name to the name and scope you own before `npm publish`.

## Starting A Session

In Claude Code, use either natural language or the installed command:

```text
/learn Python from zero; my goal is to build a Web API.
```

In Codex, the stable interface is the installed global skill. Use natural
language or explicitly mention it:

```text
Use the adaptive-learning-coach skill. Start a study session for Python.
```

Codex does not share Claude's personal `.claude/commands` directory, so the
package does not invent a non-portable Codex slash-command location.

## Project Install

For a single project, install the package without `-g`:

```text
npm install --save-dev @your-scope/adaptive-learning-coach
```

Project postinstall copies the skill to `.claude/skills` and `.cursor/skills`,
and installs `.claude/commands/learn.md`.

To select one client explicitly:

```text
npx @your-scope/adaptive-learning-coach install --scope project --client claude
npx @your-scope/adaptive-learning-coach install --scope project --client cursor
```

Inspect targets without writing files:

```text
npx @your-scope/adaptive-learning-coach install --scope global --dry-run
```

If npm lifecycle scripts are disabled, install with `--ignore-scripts` and run
the explicit installer afterward. Set `STUDYANY_SKIP_INSTALL=1` to skip the
automatic postinstall path.

## Publish

```text
npm login
npm version patch
npm publish --access public
```

Use `npm publish` without `--access public` for an unscoped package or a
private package according to your npm organization settings.

## Study Clock

The skill calls the bundled Python script when a shell tool is available:

```text
python .claude/skills/adaptive-learning-coach/scripts/study_clock.py start --subject "example" --mode lesson --objective "Complete one practice task"
python .claude/skills/adaptive-learning-coach/scripts/study_clock.py status
python .claude/skills/adaptive-learning-coach/scripts/study_clock.py stop --status complete --next-action "Review the errors"
```

On Windows, use `py -3` if `python` is not on `PATH`. The script writes an
open session to `.study/active-session.json`, then appends the measured session
to `.study/sessions.jsonl` when stopped.
