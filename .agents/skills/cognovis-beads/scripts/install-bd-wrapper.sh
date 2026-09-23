#!/bin/sh
# install-bd-wrapper.sh — Install the bd PATH-shim wrapper to ~/.local/bin/bd
#
# This makes `bd lint --check=architecture-contracts` work in any shell,
# without needing to source bd-lint-extension.sh.
#
# What this installer does:
#   1. COPIES (not symlinks) bd-wrapper to ~/.local/bin/bd
#   2. COPIES bd_lint_contracts.py to ~/.local/bin/bd_lint_contracts.py
#      (so the install is stable even after the source worktree is deleted)
#   3. Verifies that ~/.local/bin precedes the real bd in PATH
#
# Usage:
#   bash skills/cognovis-beads/scripts/install-bd-wrapper.sh           # safe install
#   bash skills/cognovis-beads/scripts/install-bd-wrapper.sh --force   # overwrite non-wrapper files
#
# Compatible with POSIX sh, bash, and zsh.

set -e

# Parse flags
_FORCE=false
for _arg in "$@"; do
    case "$_arg" in
        --force) _FORCE=true ;;
    esac
done

# Locate the install script's real directory
_SELF=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
_SCRIPT_DIR=$(dirname "$_SELF")
_WRAPPER="$_SCRIPT_DIR/bd-wrapper"
_CONTRACTS_SCRIPT="$_SCRIPT_DIR/bd_lint_contracts.py"

# Sanity checks
if [ ! -f "$_WRAPPER" ]; then
    echo "ERROR: bd-wrapper not found at $_WRAPPER" >&2
    exit 1
fi
if [ ! -f "$_CONTRACTS_SCRIPT" ]; then
    echo "ERROR: bd_lint_contracts.py not found at $_CONTRACTS_SCRIPT" >&2
    exit 1
fi

# Ensure ~/.local/bin exists
_TARGET_DIR="$HOME/.local/bin"
if [ ! -d "$_TARGET_DIR" ]; then
    echo "Creating $_TARGET_DIR ..."
    mkdir -p "$_TARGET_DIR"
fi

_TARGET="$_TARGET_DIR/bd"
_TARGET_CONTRACTS="$_TARGET_DIR/bd_lint_contracts.py"

# Copy wrapper script (not symlink — stable across worktree lifecycle).
# Remove any existing target first (handles symlinks from previous installs
# and avoids macOS cp's "source and dest are identical" error).
echo "Installing bd wrapper to $_TARGET ..."
if [ -f "$_TARGET" ] && ! grep -qF 'BD_WRAPPER_MARKER' "$_TARGET" 2>/dev/null; then
    if [ "$_FORCE" = "false" ]; then
        echo "ERROR: $_TARGET exists and is NOT a bd-wrapper (it may be another tool)." >&2
        echo "Re-run with --force to overwrite it." >&2
        exit 1
    else
        echo "WARNING: overwriting non-wrapper file at $_TARGET (--force specified)."
    fi
fi
rm -f "$_TARGET"
cp "$_WRAPPER" "$_TARGET"
chmod +x "$_TARGET"

# Copy the contracts linter alongside the wrapper
echo "Installing bd_lint_contracts.py to $_TARGET_CONTRACTS ..."
if [ -f "$_TARGET_CONTRACTS" ] && ! grep -qF 'BD_LINT_CONTRACTS_MARKER' "$_TARGET_CONTRACTS" 2>/dev/null; then
    if [ "$_FORCE" = "false" ]; then
        echo "ERROR: $_TARGET_CONTRACTS exists and is NOT a bd_lint_contracts install." >&2
        echo "Re-run with --force to overwrite it." >&2
        exit 1
    else
        echo "WARNING: overwriting non-contracts file at $_TARGET_CONTRACTS (--force specified)."
    fi
fi
rm -f "$_TARGET_CONTRACTS"
cp "$_CONTRACTS_SCRIPT" "$_TARGET_CONTRACTS"

echo ""
echo "Installed:"
echo "  $_TARGET"
echo "  $_TARGET_CONTRACTS"

# ---------------------------------------------------------------------------
# Verify PATH precedence: ~/.local/bin must appear BEFORE the real bd binary
# ---------------------------------------------------------------------------
echo ""
echo "Checking PATH precedence ..."

# Check if ~/.local/bin is in PATH at all
case ":$PATH:" in
    *":$_TARGET_DIR:"*)
        : # it is in PATH, continue to precedence check below
        ;;
    *)
        echo ""
        echo "IMPORTANT: $_TARGET_DIR is not in your PATH."
        echo "Add it by appending one of the following to your shell config:"
        echo ""
        echo "  For bash (~/.bashrc or ~/.bash_profile):"
        echo '    export PATH="$HOME/.local/bin:$PATH"'
        echo ""
        echo "  For zsh (~/.zshrc):"
        echo '    export PATH="$HOME/.local/bin:$PATH"'
        echo ""
        echo "  Then restart your shell or run: source ~/.bashrc  (or ~/.zshrc)"
        echo ""
        echo "After adding ~/.local/bin to PATH, run this installer again to verify."
        exit 0
        ;;
esac

# Check that 'bd' resolves to our installed wrapper (not the real binary)
_resolved_bd=$(command -v bd 2>/dev/null || echo "")
if [ -z "$_resolved_bd" ]; then
    echo "WARNING: 'bd' not found in PATH at all. Add ~/.local/bin to PATH and restart shell."
elif [ "$_resolved_bd" = "$_TARGET" ]; then
    echo "PATH precedence OK — 'bd' resolves to the installed wrapper."
    echo ""
    echo "Ready to use:"
    echo "  bd lint --check=architecture-contracts"
else
    # Resolve symlinks to compare
    _resolved_target=$(readlink -f "$_resolved_bd" 2>/dev/null || realpath "$_resolved_bd" 2>/dev/null || echo "$_resolved_bd")
    _our_target=$(readlink -f "$_TARGET" 2>/dev/null || realpath "$_TARGET" 2>/dev/null || echo "$_TARGET")
    if [ "$_resolved_target" = "$_our_target" ]; then
        echo "PATH precedence OK — 'bd' resolves to the installed wrapper."
        echo ""
        echo "Ready to use:"
        echo "  bd lint --check=architecture-contracts"
    else
        echo ""
        echo "WARNING: 'bd' resolves to '$_resolved_bd', not the installed wrapper."
        echo "This means $_TARGET_DIR does not precede the real bd in PATH."
        echo ""
        echo "Fix: ensure ~/.local/bin appears BEFORE other directories in PATH:"
        echo ""
        echo "  For bash (~/.bashrc or ~/.bash_profile):"
        echo '    export PATH="$HOME/.local/bin:$PATH"'
        echo ""
        echo "  For zsh (~/.zshrc):"
        echo '    export PATH="$HOME/.local/bin:$PATH"'
        echo ""
        echo "  Then restart your shell and verify with: which bd"
    fi
fi
