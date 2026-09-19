# BuildTrack — Team Planning & Approval Desktop App

A desktop project-planning tool built with **Python + Tkinter + SQLite**, originally developed for a construction-management team and rewritten here with anonymized sample data for demonstration purposes.

> This is a sanitized portfolio version of a real internal tool I built and still maintain for my employer. Company names, logos and real employee names have been replaced with fictional placeholders ("BuildTrack", sample users). The architecture, features and code are otherwise representative of the production system.

## Why I built this

The team I work with plans construction jobs across two independent crews, and needed a lightweight way to:
- Submit and review daily work plans, with review responsibilities scoped strictly per crew (no cross-crew visibility).
- Track tasks and projects with comments and file attachments.
- Coordinate planned vacation and early-leave requests on a shared calendar, without losing visibility while a request is still pending approval.
- Do all of this offline, on a single shared machine per site, without needing a server or a monthly SaaS subscription.

Existing tools (Microsoft Planner and similar) were either too generic or didn't model the team's actual approval structure, so I built something tailored to it.

## Features

**Plan submission & review**
- Daily plans submitted per user, routed to reviewers.
- Review visibility is scoped by group: each crew only sees and reviews plans from its own crew. One reviewer role can review across all crews.
- Members outside a crew cannot see that a plan exists there at all — not the submission, not who reviewed it.

**Tasks & projects**
- Tasks with priority, linked project, and manual ordering.
- Per-task discussion thread with file attachments.
- One-click "open project folder" from the app.

**Team calendar**
- Planned vacation stays visible on the shared calendar from the moment it's requested (instead of disappearing until approved), so the team can plan around it.
- A designated approver marks it as confirmed; the calendar entry changes color accordingly.
- Early-leave / end-of-shift requests scoped to presence groups, with a minimum on-site coverage rule.

**Internal messaging**
- Simple broadcast/point-to-point messages between users, with read/unread tracking.

**Accounts & security**
- Passwords stored as salted PBKDF2 hashes — never in plain text.
- Legacy plain-text passwords are transparently migrated to the hashed format on first login after an upgrade.
- Users can change their own password from the sidebar.
- Manual database backup (available to manager-level roles), timestamped into a local `backups/` folder.

## User roles (sample data)

| Role | Typical access |
|---|---|
| `trabalhador` (worker) | Submits plans, tasks and messages; sees calendar and shift data for their own crew |
| `planejador` / `chefe` / `gestor` (planner / lead / manager) | Team-wide overview, reviews plans for their crew, can back up the database |
| Cross-crew reviewer | Reviews plans from every crew |
| Approver | Confirms planned vacation requests |

## Tech stack

- **Python 3**, standard library only for core logic
- **Tkinter** for the desktop UI (no external UI framework)
- **SQLite3** for local, file-based storage — no server required
- Password hashing via `hashlib.pbkdf2_hmac` (stdlib, no third-party crypto dependency)

## Project structure

```
├── app.py           # Full application: UI + business logic + data access
├── .gitignore        # Excludes the local database, backups/ and anexos/ (attachments)
```

## Running locally

```bash
git clone <this-repo-url>
cd buildtrack
python app.py
```

On first run, the SQLite database, the attachments folder and the sample users listed above are created automatically. Every sample account uses the password `<username>123` (e.g. `alex` / `alex123`) — change it after logging in via the "Trocar senha" (Change password) option in the sidebar.

## Design notes

- **Group-scoped visibility is enforced at the query/permission layer**, not just hidden in the UI — functions like `pode_ver_solicitacao()` and `pode_conferir_plano()` centralize every access rule, which keeps the permission logic auditable and easy to unit test in isolation from the UI.
- **Password migration is lazy, not a one-off script.** Old plain-text passwords upgrade to hashed storage automatically the first time a user logs in after the update, so there's no maintenance window or forced mass password reset.
- **No external dependencies.** Everything runs from a stock Python install on Windows, which matters for a small team without IT infrastructure to maintain a server or manage a package environment.

## What I'd improve next

- Split the single-file application into modules (data access / calendar / reviews / UI) as it keeps growing.
- Move from one SQLite connection per function call to a shared connection/session pattern.
- Add automated tests around the permission functions, since those are the most safety-critical part of the app.

---

*Feel free to reach out if you'd like to discuss the architecture or see the full (internal) version in a call.*
