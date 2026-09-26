# IBVAP — Team Workflow

**No Git. Manual folder-copy, with one shared contract file and one safety habit.**
This document is what makes that safe.

---

## Roles

- **Module owner (each teammate):** works entirely inside their own copy of their one
  assigned module folder. Never touches another module's folder, the root docs, or
  `modules/_shared/CONTRACTS.md`.
- **Lead (you):** the single point where a finished module folder becomes "official."
  The only person who edits `modules/_shared/CONTRACTS.md`.

---

## If You're a Module Owner

1. You'll receive: your module folder (5 files), this `WORKFLOW.md`, the shared
   `CONTRACTS.md`, and a `reference/` folder with the full system docs for context.
2. Do all your work — code and doc updates — **inside your own copy of your module
   folder only.**
3. If your module needs something from another module's data (an event, a field) that
   isn't already described in `CONTRACTS.md`, **ask the lead.** Don't guess at it or add
   it in your own copy — your copy of the contract has to match everyone else's.
4. As you work, keep your module's `PRD.md` status header current (see Status Values
   below) — it's how the lead knows what state you're in without having to ask.
5. When you believe it's done, hand your whole folder back to the lead. You don't merge
   it yourself — that's the one step reserved for the lead, on purpose.

---

## If You're the Lead

1. Receive a teammate's finished module folder.
2. **Archive the current official version before touching anything:**
   ```
   cp -r modules/<module-slug> modules/_archive/<module-slug>-<YYYY-MM-DD>
   ```
   Do this every time, even for a small fix. It's your only undo button without Git.
3. Review the incoming folder:
   - Does `PRD.md` actually deliver what it claims?
   - Does `RULES.md` get followed (no hardcoded thresholds, no single-parameter
     critical triggers, etc.)?
   - Does `ARCHITECTURE.md`'s "Outputs" section still match `CONTRACTS.md`? If a
     teammate needed a new field, did they ask you, or did they just add it?
4. **If it's good:** copy it over the official `modules/<module-slug>/` folder,
   overwriting it.
5. **If it needs fixes:** copy it to a scratch workspace, make the edits there,
   re-review, then copy the corrected version in — still archiving the previous
   official version first (step 2 always comes first, no exceptions).
6. Update the Module Index table in the root `ARCHITECTURE.md` (§4) — Owner and Status —
   to match what just happened.

---

## Status Values

Used in the header of every module's `PRD.md`:

| Status | Meaning |
|---|---|
| `Not Started` | Folder exists, nobody's touched it yet |
| `In Progress` | Owner is actively working in their own copy |
| `Ready for Review` | Owner has handed their folder back to the lead |
| `Changes Requested` | Lead sent it back with notes; owner is revising |
| `Merged` | Lead has copied it into the official `modules/` folder — this is the only status that means "official" |

Only a folder inside `modules/` with `Status: Merged` should be treated as the current
truth for that module. Anything else is a work-in-progress copy somewhere else.

---

## The One Shared File Rule

`modules/_shared/CONTRACTS.md` defines every event and interface that crosses module
boundaries. **Only the lead edits it.** If a module needs a new event or a changed
field, that's a conversation with the lead, not a unilateral edit — because the whole
point of the file is that everyone is looking at the same version of it.

## The Archive Habit

Before overwriting any official module folder, copy the current version into
`modules/_archive/<module-slug>-<date>/`. See `modules/_archive/README.md`. This one
habit is what turns "manual folder copying" from risky into safe.

---

## What This Actually Protects You From

- **A teammate's incomplete or broken work never touches anything else**, because
  nothing becomes official until the lead has reviewed it and copied it in personally.
- **A bad merge is always recoverable**, because the previous version was archived
  first, every time, without exception.
- **Nobody can quietly redefine what an event or interface looks like** on their own,
  because `CONTRACTS.md` has exactly one editor.
- **You can open any module folder and know, from its `PRD.md` status line alone,
  whether what you're looking at is trustworthy** — without having to read the whole
  thing first.
