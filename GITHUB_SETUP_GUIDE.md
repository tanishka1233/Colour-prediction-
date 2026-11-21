# GitHub Setup Guide (simple steps)

## What is already done locally

1. Git was initialized in the project folder (it did not exist before).
2. All source, docs, tests and Phase 0 investigation files were added.
3. Runtime files were **not** added: SQLite databases, logs, `.env`, backups and Python cache are ignored by `.gitignore`.
4. A secret scan found **0 probable secrets** in 115 scanned files.
5. First commit: `0d6672f` on branch `main`.
6. Remote `origin` was added with the URL you gave:
   `https://github.com/tanishka1233/Colour-prediction-.git`

## What exists on GitHub right now

The remote already had a branch called `main-/-root` containing only `1.html` and `README.md`.
We did **not** delete, reset or overwrite it. Our work is pushed as a **new branch** called `main`
(or another name if a push needed a different target — see final report).

## How to push (if it was not already done)

In your project folder:

```bash
git remote -v                       # confirm origin URL
python3 scripts/secret_scan.py      # must print 0 findings
git push -u origin main
```

If GitHub asks for a username/password, use a **Personal Access Token** as the password.
Never type a token into a file, a workflow, or a report.

## After pushing

1. Open the repository on GitHub.
2. You will see both branches. Open the new branch.
3. If you want the code on the default branch, create a Pull Request from `main` into `main-/-root`, review it, then merge.
   (We did not merge automatically because that changes the existing branch.)

## Useful safety commands

```bash
git status --short --branch         # what changed locally
git log --oneline -5                # recent commits
git diff --stat                     # summary of uncommitted changes
git check-ignore -v data/hmx.sqlite3  # confirm DB is ignored
```

## Never commit

- `.env` or any token/password
- `data/*.sqlite3` and WAL/SHM files
- `logs/*.jsonl`
- backup files or database copies
- browser cookies or session data
