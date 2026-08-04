# Artifact Workflow

Use this workflow when the learning objective is best demonstrated by a
concrete result outside the conversation. An artifact may be a file, a result
from an external tool, a completed procedure, a physical performance, or
another inspectable output. The medium is selected from the evidence required
by the objective, not from the subject label.

## Choose the medium

Use `conversation` when the learner can demonstrate the objective through
unaided recall, explanation, comparison, planning, reasoning, or feedback in
the dialogue.

Use `artifact` when the learner must edit, run, manipulate, produce, observe,
or repeat something outside the dialogue and that result is necessary
evidence.

Use `mixed` when the learner needs a short explanation or retrieval exchange
and an external result. This is the default for many procedural tasks, but do
not force it when conversation alone is sufficient.

## Resolve the artifact language

Before creating or substantially editing an artifact, read
`references/output-language.md`. Resolve the language from the learner's
current request, `profile.json.language`, or the current conversation. Use it
for comments, docstrings, instructions, labels, sample text, notebook prose,
spreadsheet notes, and the artifact handoff. Keep code keywords, API names,
commands, identifiers required by an existing project, paths, schema fields,
and exact contract output unchanged when they must remain interoperable.

Do not translate an existing non-empty file automatically. Preserve its
language and style unless the learner requests translation; new companion
files use the resolved language. A mixed-language artifact must have a stated
technical reason for each exception.

## Prepare the workspace

1. Check whether the learner already supplied a file, project, workbook,
   document, dataset, media item, tool state, or other working material. Use
   that material when it is available and appropriate.
2. If no suitable material exists, create the smallest useful starter,
   template, checklist, test, fixture, prompt sheet, or other scaffold. Tell
   the learner exactly what was created and why.
3. Keep learner-editable files visible in the current project workspace. If
   the learner has not supplied a project path, use the root-level directory
   `studyany-artifacts/<goal-slug>/` by default. For a project-specific
   objective, prefer a visible path inside the learner's project, such as its
   existing source or exercise directory. If the learner explicitly chooses a
   different path, use that path instead. `.study/` is reserved for internal
   records and must not be the default location for files the learner needs to
   open or edit.
4. Keep the path project-relative in the record when possible, and show the
   exact path in the learner handoff. The learner should be able to find the
   file from the project root without searching hidden directories.
5. Never overwrite a non-empty learner file. Choose a new filename or ask
   before replacing it. Do not silently modify unrelated project files.
6. A starter is not evidence of mastery. Leave meaningful decisions and work
   for the learner unless the objective explicitly calls for analysis of a
   provided example.
7. Before handing off the file, check that learner-readable content uses the
   resolved language and record that language as `content_language` in the
   artifact event.

## Give the learner a usable handoff

Every artifact or mixed lesson states all four items:

```text
Workspace: <where to work>
Artifact: <file, tool state, or external reference>
Learner action: <the exact change or performance to complete>
Review evidence: <what to return, run, show, or explain>
```

For a generated local file, include a visible relative path, for example:

```text
Workspace: project root
Artifact: studyany-artifacts/topic-name/starter.py
Learner action: Open the file from the project root and complete the marked task
Review evidence: Return the diff or execution output
```

The English wording in this structural example is a placeholder only. Replace
the labels and prose with the resolved learner language in the actual handoff.
The path, learner action, review evidence, comments, and instructions in the
handoff must use the same resolved learner language. Preserve exact technical
tokens in paths, commands, code, and external contract text.

The learner action should be small enough for the current session and should
include a quality bar or completion condition. If a command, application, or
physical setup is required, state the prerequisite and the expected output
without claiming that it has already run.

## Review the result

After the learner acts:

- Inspect the file, diff, output, or result with available tools when the
  learner has given access to it.
- Otherwise ask for the smallest useful evidence: a path, diff, excerpt,
  screenshot, output, self-recorded observation, or explanation as appropriate.
- Compare the result with the session objective and rubric, not merely with a
  reference answer.
- Identify the first consequential error, ask for a correction or nearby
  variation, and record what was actually observed.
- Separate `submitted` from `reviewed`; possession of a file is not proof that
  the learner understands or can reproduce the skill.

Never claim to have opened, executed, calculated, rendered, or verified an
artifact unless the environment or learner supplied that evidence. If the
artifact is unavailable, record `missing_evidence` and keep the next action
small.

## Record lifecycle

Create an artifact record when a workspace item is planned or supplied. Update
its status as the learner works:

```text
planned -> in_progress -> submitted -> reviewed
```

Use `abandoned` when the task is intentionally dropped. Link the artifact to
the current session and any assessment. Record the path or external reference,
kind, learner action, expected evidence, review status, and evidence reference;
record `content_language`; do not duplicate the full artifact contents in
`.study/` logs.
