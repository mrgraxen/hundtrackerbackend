# GitHub setup – step-by-step (beginner)

This guide gets your Hundtracker backend on GitHub and keeps everything in sync. No prior Git/GitHub experience required.

---

## Part 1: Create the repo on GitHub (once)

1. **Log in** to [github.com](https://github.com) (account: **mrgraxen**).

2. **Create a new repo**
   - Click the **+** (top right) → **New repository**.
   - **Repository name:** `hundtrackerbackend` (no spaces).
   - **Description:** optional, e.g. "Backend for Hundtracker hunter tracker app".
   - **Private** (recommended).
   - **Do not** check "Add a README file", ".gitignore", or "License" – your project already has these.
   - Click **Create repository**.

3. Leave the browser tab open; you’ll need the repo URL in Part 3.

---

## Part 2: Prepare your project on your PC (once per machine)

Open **PowerShell** or **Command Prompt** and go to your project folder:

```powershell
cd "C:\Users\graxe\Hundtrakcer backend"
```

### Check if Git is already set up

```powershell
git status
```

- If you see "not a git repository": run the **First-time setup** below.
- If you see "On branch main" and a list of files: skip to **Part 3**.

### First-time setup (only if needed)

```powershell
git init
git branch -M main
git add .
git status
```

You should see all your files (app, docs, Dockerfile, etc.) listed as "to be committed". Then:

```powershell
git commit -m "Initial commit: Hundtracker backend"
```

Now connect the folder to your GitHub repo (use your real repo URL):

```powershell
git remote add origin https://github.com/mrgraxen/hundtrackerbackend.git
```

If you already had a remote and it was wrong:

```powershell
git remote set-url origin https://github.com/mrgraxen/hundtrackerbackend.git
```

---

## Part 3: Push to GitHub

```powershell
git push -u origin main
```

- **If it asks for username:** `mrgraxen`
- **If it asks for password:** do **not** use your GitHub login password. Use a **Personal Access Token** (see below).

### Creating a Personal Access Token (for private repo)

1. GitHub (top right) → **Settings**.
2. Left sidebar → **Developer settings** → **Personal access tokens** → **Tokens (classic)**.
3. **Generate new token (classic)**.
4. **Note:** e.g. "Hundtracker push".
5. **Expiration:** 90 days or "No expiration" (your choice).
6. **Scopes:** check **repo** (full control of private repositories).
7. Click **Generate token**.
8. **Copy the token** (starts with `ghp_...`) and store it somewhere safe. You won’t see it again.
9. When Git asks for a password, **paste this token**, not your GitHub password.

After a successful push, refresh the repo page on GitHub – you should see all your files and folders.

---

## Part 4: What happens next (CI/CD in simple terms)

- **Git** = version control (your code history).
- **GitHub** = place where that history lives online.
- **CI/CD** = when you push, GitHub can automatically build and publish things for you.

In this project:

1. You push code to `main` (as in Part 3).
2. A **GitHub Action** (workflow) runs automatically.
3. It **builds** a Docker image of your backend.
4. It **pushes** that image to **GitHub Container Registry (GHCR)** so you (or RunTipi) can run it without building on your machine.

You can watch it run:

- On the repo page: **Actions** tab → click the latest "Publish to GHCR" run.
- When it’s green, the image is at: `ghcr.io/mrgraxen/hundtracker-backend:latest`.

You don’t have to run any commands for this; it happens on GitHub’s side.

---

## Part 5: Later – making changes and pushing again

When you change code or docs:

```powershell
cd "C:\Users\graxe\Hundtrakcer backend"
git add .
git status
git commit -m "Short description of what you changed"
git push
```

- `git add .` = stage all changes.
- `git commit` = save a snapshot with a message.
- `git push` = send that snapshot to GitHub (and trigger the workflow again if you’re on `main`).

---

## Quick reference

| Goal                    | Command |
|-------------------------|--------|
| See repo URL            | `git remote -v` |
| See status              | `git status` |
| Push to GitHub          | `git push -u origin main` (first time), then `git push` |
| After changing files    | `git add .` → `git commit -m "message"` → `git push` |

If something doesn’t match (e.g. different repo name or username), change the URLs in this guide to match your repo: `https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git`.
