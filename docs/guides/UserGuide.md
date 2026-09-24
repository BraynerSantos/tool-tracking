# User Guide — how the app works

This guide explains what the application is, what every part of it does, and
how to do the day-to-day tasks. No computer knowledge needed beyond using a
browser.

## What the app is

A single web page that answers one question fast: **"do we have this tool, and
where is it?"** — plus a permanent record of every change made.

- It runs on one PC (the server). Everyone else opens it in a browser.
- All data lives in **one file** (`tooldb.sqlite` next to the exe). Nothing is
  stored on employee PCs.
- Every change is recorded: who made it, when, and what changed (each tool's
  **History** section).

## The building blocks

| Thing | What it is | Example |
|---|---|---|
| **Employee** | A person who can log in, identified by badge ID | `000`, `E106` |
| **Admin** | An employee who can also manage setup (people, departments, tool types, backups) | usually a supervisor |
| **Department** | A group of the shop (where tools live) | Milling, Grinding, QC |
| **Location** | A named spot inside a department | Cabinet 3, Crib shelf B |
| **Tool type** | A category of tool, with the list of attributes that describe it | "End mills" have diameter, flutes, coating |
| **Attribute** | One descriptive fact about a tool — text or number | Diameter (mm) = 6.35 |
| **Tool** | One entry in the catalog: a type + its attributes + how many exist | 6 mm carbide end mill, TiAlN |
| **Inventory** | How many of that tool are at each location | 12 in Milling/Cabinet 3, 4 in QC/Shelf 2 |

Two ideas worth internalizing:

1. **Quantities, not serial numbers.** The app tracks *how many* of a tool
   exist and *where* — not each physical piece individually.
2. **Tool types are yours.** The app starts with none. Admin creates the
   categories the shop actually uses, and decides which attributes each one
   has. Deleting a type that no tools use is safe; a type with tools refuses
   to be deleted until they're moved or removed.

## Logging in

Type your **badge ID** on the login page. The app suggests matching names
after a couple of characters — click yours. There is no password; the badge
*is* the identity, so don't make changes under someone else's login.

## Searching (the main screen)

The big box searches **everything at once**: tool names, descriptions, and
every attribute value. Typing `6.35`, `HSK`, `TiAlN`, or `caliper` all work.

- Filters narrow by **tool type**, **department**, or **location**.
- Results show each tool's total quantity and a per-location breakdown
  (e.g. `Milling – Cabinet 3: 12 · QC – Shelf 2: 4`).
- **Low stock**: if a tool has a reorder minimum set, it shows an amber
  "low stock" badge whenever the total is at or below that number.
- Your search + filters are in the address bar, so you can bookmark or share
  a link to a specific search.

## Adding a tool

Click **+ Add tool**:

1. Pick the **tool type** — the attribute fields below change to match it.
2. Fill name (required), description, and any attributes you know (blank is
   fine).
3. **Reorder minimum** (optional): set it and the tool flags itself "low
   stock" when the total drops to that number.
4. Add one or more **location + quantity** rows. Quantities are whole
   numbers, never negative.
5. Save. The tool appears in search immediately.

Decimals are fine for number attributes (0.250, 6.35) — that's normal for
inch-sized tooling.

## Editing quantities and details

Open a tool (click its name in search) → **Edit**. Change what you need.
Replacing the location quantities *replaces the whole set* — enter every
location and its new count, not just the changed one. Deleted tools are gone
for good (a confirmation asks first), but their history stays in the audit
log.

## Export and print

Both buttons act on **exactly what you currently see** — your search and
filters — not the whole catalog:

- **Export CSV** downloads a spreadsheet-compatible file.
- **Print** gives a clean printed list (no menus or buttons on the paper).

## History

Every tool's detail page lists its change history: date/time, badge ID of who
made the change, what they did. This is the record for "who changed this?"

## If something looks wrong

Refresh the page first (F5) — you may be looking at a stale view. If a tool
is genuinely wrong, fix it via Edit; if you can't tell what happened, check
its History, then talk to an admin.
