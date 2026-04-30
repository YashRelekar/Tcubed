# Ported From

| Field            | Value                                         |
|------------------|-----------------------------------------------|
| **Source repo**  | `Phatshark05/2002`                            |
| **Source repo ID** | `1219671575`                                |
| **Import date**  | `2026-04-30`                                  |
| **Imported by**  | Copilot coding agent (copilot-swe-agent)      |

## Import Strategy

Files from `Phatshark05/2002` are ported using the following strategy:

1. **Direct mirror** — files whose paths do not conflict with any existing file in
   `YashRelekar/Tcubed` are placed at the same relative path as in the source repo.

2. **`ported/2002/` sub-tree** — files whose paths *would* conflict with an existing
   file in `YashRelekar/Tcubed` are placed under `ported/2002/<original-relative-path>`
   so that the destination's existing content is always preserved.

## Status

> ⚠️ **Automatic porting could not be completed.**
>
> The source repository `Phatshark05/2002` (ID `1219671575`) is **private**, and the
> Copilot coding agent was not granted installation access to it.  The agent holds a
> GitHub App token scoped only to `YashRelekar/Tcubed`; all attempts to clone or read
> the source repository returned HTTP 403.
>
> **To complete the port, one of the following actions is required:**
>
> 1. **Grant the Copilot coding agent access to `Phatshark05/2002`** by installing the
>    [GitHub Copilot coding agent app](https://github.com/apps/copilot-swe-agent) on
>    that repository, then re-run this task.
>
> 2. **Manually copy the files** from `Phatshark05/2002` into this repository, placing
>    non-conflicting files at their original relative paths and conflicting files under
>    `ported/2002/<original-path>`.  Then update this document to reflect the final
>    state.

## Conflict Policy

If a path exists in *both* `Phatshark05/2002` and `YashRelekar/Tcubed` the incoming
file is placed at `ported/2002/<original-relative-path>` and the existing file is
left untouched.

The `ported/2002/` directory structure mirrors the source repo layout exactly beneath
the `ported/2002/` prefix.
