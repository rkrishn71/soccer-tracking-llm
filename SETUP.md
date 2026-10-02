# Local setup (macOS + VS Code + GitHub)

Rebuilds Phase 1 from scratch on your machine, checks that the result matches the original
build exactly, and puts the project under git on a private GitHub repo.

**Time:**
- About 10 minutes of commands.
- About 5 minutes to download the data.
- About 5–10 minutes for the build.
- About 2 minutes for the tests.

**Disk:** about 2.5 GB in total.

## 0. One-time prerequisites

Install [Homebrew](https://brew.sh) if you don't have it, then:

```bash
brew install python@3.11 git git-lfs gh
gh auth login            # GitHub.com → HTTPS → "Login with a web browser"
```

- **Python must be 3.11 or newer**, because pandas 3 requires it.
- **git-lfs** is needed for the SkillCorner tracking files.
- **gh** is the GitHub CLI. It creates the repo and pushes with your own login.

## 1. Unzip and enter the project

```bash
mkdir -p ~/code && cd ~/code
unzip ~/Downloads/soccer-tracking-llm.zip      # creates ~/code/soccer-tracking-llm
cd soccer-tracking-llm
```

## 2. Commit the untouched Cowork state first

Do this **before** running anything, so every later change shows up as a diff.

```bash
git init -b main
git add -A
git commit -m "Phase 1 (Cowork-generated)"
```

`.gitignore` already excludes `data/` and `.venv/`. The commit holds about 35 small files:
code, docs, tests, the notebook and the reference numbers.

## 3. Create the private GitHub repo and push

```bash
gh repo create soccer-tracking-llm --private --source=. --remote=origin --push
```

If you prefer the website: create an **empty** private repo called `soccer-tracking-llm`, with
no README or .gitignore, then run:

```bash
git remote add origin https://github.com/<your-username>/soccer-tracking-llm.git
git push -u origin main
```

## 4. Python environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Data, build, tests, verification

```bash
bash scripts/setup_data.sh          # clones both repos at the pinned commits, pulls + checks LFS
python -m src.build                 # writes data/processed/ (23 parquet + meta files)
python -m pytest -q                 # expect: 218 passed (warnings are the off-pitch reports)
python scripts/verify_phase1.py     # expect: "OK - every count matches the original Phase 1 build"
python scripts/check_conventions.py # expect: "OK: 38 cited lines verified"
```

What success looks like:

- `pytest` reports 218 passed.
- `verify_phase1.py` reports **31,840,119 total rows** and no differences.

If both hold, the pipeline is reproducible on your machine and not just in Cowork.

If `verify_phase1.py` lists differences:

- Do not edit the reference file.
- First check `git -C data/raw/skillcorner_opendata rev-parse HEAD`. It must start with `4340d27`.

## 6. VS Code

```bash
code .
```

(If `code` isn't found: in VS Code press Cmd-Shift-P and run "Shell Command: Install 'code' command in PATH".)

1. Accept the prompt to install the recommended extensions: Python, Pylance and Jupyter.
2. The interpreter is preset to `.venv/bin/python`. If VS Code asks, choose that one. Otherwise use Cmd-Shift-P → "Python: Select Interpreter".
3. **Testing** panel (beaker icon): the 218 tests appear there and can be run one at a time.
4. Open `notebooks/phase1_checks.ipynb` and pick the `.venv` kernel (top right). Run All re-draws the frame plots.

## 7. Day-to-day

```bash
source .venv/bin/activate
git switch -c phase2/usable-frames     # one branch per piece of work
# ... edit, run pytest ...
git add -A && git commit -m "..." && git push -u origin HEAD
```

- **What gets committed:** code, docs, tests and notebooks.
- **What never gets committed:** `data/`, which is about 2.5 GB.
- **Rebuilding the data:** anyone can regenerate it with steps 4–5.
