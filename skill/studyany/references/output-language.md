# Learner Language For Generated Outputs

Use this reference whenever StudyAny creates or substantially edits a
learner-facing file, report, template, notebook, workbook, fixture, or other
artifact. The learner's current language applies to the readable support
content of the artifact, not to tokens that must remain executable or
interoperable.

## Resolve the language

Choose one language for the output using this precedence:

1. An explicit language request in the current turn.
2. The current learner-facing language in `profile.json.language`.
3. The language used by the current conversation.
4. One short clarification question when the signals conflict materially.

Use a practical BCP 47-style value when recording it, such as `zh-CN`, `en`,
or `ja`. Do not infer the output language from the subject, programming
language, source material, or file extension. A learner may study Python in
Chinese, or study a Chinese subject in English.

If the learner changes language in the current request, use the new language
for new output without rewriting existing artifacts unless they ask for a
translation. Do not repeatedly ask for the language when the current choice is
clear.

## What must be localized

Use the resolved language for every new learner-readable part of a generated
artifact, including:

- code comments, docstrings, explanatory strings, TODOs, and exercise prompts;
- Markdown, README text, notebook prose, headings, labels, and checklists;
- workbook or spreadsheet sheet names, headers, cell instructions, and notes;
- sample input and output text when it is not constrained by an external API;
- test descriptions, fixture explanations, and the file handoff shown in chat;
- generated feedback pages, badges, summaries, and progress reports.

For `.study` records, keep machine field names and enum values exactly as the
schema defines them, but write human-readable values such as `summary`,
`notes`, `learner_action`, `expected_evidence`, and `review_notes` in the
resolved learner language.

Do not add English comments or instructional prose merely because the subject
is technical. Use the user's language to make the artifact a learning aid.

## What must remain exact

Do not mechanically translate tokens whose spelling or structure is part of
the task:

- programming-language keywords, standard-library names, API names, package
  names, protocol fields, command names, URLs, file paths, and environment
  variables;
- identifiers that must match an existing codebase, schema, test, or external
  interface;
- exact output, error text, or data values required by a test or contract.

When an identifier or API is conventionally English, keep it if changing it
would reduce correctness or follow the surrounding project convention. Explain
its meaning in the learner's language and localize nearby comments, labels, and
user-facing strings. If a user-facing string is intentionally required to be
English by an external contract, state that exception and provide the
learner-facing explanation in the resolved language.

## Existing artifacts

Inspect an existing file before editing it. Preserve its established language
and style unless the learner asks to translate it or the new section needs to
follow the current learner language. Never rewrite a non-empty artifact merely
to localize it. When creating a new companion file, use the resolved language
and make the relationship to the existing file clear.

## Final language check

Before handing off a generated artifact, check:

1. comments and instructional prose use the resolved language;
2. required technical tokens were preserved exactly;
3. user-facing sample strings are localized unless a contract forbids it;
4. the artifact record includes `content_language`;
5. the path, learner action, and review evidence in the handoff use the same
   language.

If the file contains intentionally mixed languages, identify the reason rather
than presenting the mixture as accidental.
