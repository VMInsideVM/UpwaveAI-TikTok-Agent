# Implementation Plan - Fix Dark Mode Floating Window Borders

## Problem
In dark mode, floating windows (User Dropdown, Report Cards, etc.) were missing visible borders. This was caused by the usage of undefined CSS variables like `--dark-border` and `--dark-bg-elevated`.

## Solution
Defined the missing CSS variables in the `[data-theme="dark"]` block in `static/index.html`.

## Changes
- **File**: `static/index.html`
- **Action**: Added definitions for:
  - `--dark-bg-primary`
  - `--dark-bg-elevated`
  - `--dark-bg-secondary`
  - `--dark-bg-tertiary`
  - `--dark-border` (set to `var(--gold-soft)`)
  - `--dark-text-primary`
  - `--dark-text-secondary`
  - `--dark-text-muted`
  - `--glass-dark`

## Verification
- Verify that `var(--dark-border)` is now defined.
- Verify elements using this variable (User Dropdown, Report Cards, etc.) now have a visible border in dark mode.
