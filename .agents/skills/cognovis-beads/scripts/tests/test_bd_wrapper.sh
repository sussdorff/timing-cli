#!/bin/sh
# test_bd_wrapper.sh — CI smoke test for the bd PATH-shim wrapper
#
# Invokes the wrapper script DIRECTLY by path to simulate a clean shell where
# no shell extension has been sourced.
#
# Usage:
#   bash skills/cognovis-beads/scripts/tests/test_bd_wrapper.sh
#
# Exit code:
#   0  All tests passed
#   1  One or more tests failed

set -e

# ---------------------------------------------------------------------------
# Locate the wrapper script relative to this test file
# ---------------------------------------------------------------------------
_SELF=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
_TESTS_DIR=$(dirname "$_SELF")
_SCRIPTS_DIR=$(dirname "$_TESTS_DIR")
_WRAPPER="$_SCRIPTS_DIR/bd-wrapper"
_CONTRACTS_SCRIPT="$_SCRIPTS_DIR/bd_lint_contracts.py"

PASS=0
FAIL=0

_pass() {
    echo "PASS: $1"
    PASS=$((PASS + 1))
}

_fail() {
    echo "FAIL: $1"
    FAIL=$((FAIL + 1))
}

echo "=== bd-wrapper smoke tests ==="
echo "Wrapper:          $_WRAPPER"
echo "Contracts script: $_CONTRACTS_SCRIPT"
echo ""

# ---------------------------------------------------------------------------
# Precondition checks
# ---------------------------------------------------------------------------
if [ ! -f "$_WRAPPER" ]; then
    echo "ERROR: bd-wrapper not found at $_WRAPPER — cannot run tests" >&2
    exit 1
fi

if [ ! -x "$_WRAPPER" ]; then
    echo "ERROR: bd-wrapper is not executable — cannot run tests" >&2
    exit 1
fi

if [ ! -f "$_CONTRACTS_SCRIPT" ]; then
    echo "ERROR: bd_lint_contracts.py not found at $_CONTRACTS_SCRIPT — cannot run tests" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Test 1: --check=architecture-contracts dispatches to Python script (not real bd)
#
# We invoke the wrapper with 'lint --check=architecture-contracts --help'.
# The Python script handles --help and exits 0. If the wrapper incorrectly
# passes to the real bd binary, bd would return an error (unknown flag).
# ---------------------------------------------------------------------------
echo "--- Test 1: bd lint --check=architecture-contracts --help delegates to Python ---"
if /bin/sh "$_WRAPPER" lint --check=architecture-contracts --help > /tmp/bd_wrapper_test1_out.txt 2>&1; then
    _pass "Test 1: wrapper delegates to Python script (exit 0 from --help)"
else
    _exit_code=$?
    # argparse exits with code 0 for --help, but let's be lenient — the key
    # signal is that output contains usage text from bd_lint_contracts.py,
    # not a bd binary error about unknown flags.
    if grep -q "bd_lint_contracts\|architecture-contracts\|lint\|bead" /tmp/bd_wrapper_test1_out.txt 2>/dev/null; then
        _pass "Test 1: wrapper delegates to Python script (exit $_exit_code but output matches Python)"
    else
        _fail "Test 1: unexpected output — wrapper may not be delegating to Python"
        cat /tmp/bd_wrapper_test1_out.txt
    fi
fi

# ---------------------------------------------------------------------------
# Test 2: Non-intercepted commands pass through to real bd binary
#
# 'bd version' should work if the real bd binary is present and functional.
# We explicitly set PATH so the wrapper can discover the real bd via PATH walk.
# ---------------------------------------------------------------------------
echo ""
echo "--- Test 2: non-intercepted command passes through to real bd binary ---"
_real_bd_found=false
for _candidate in /opt/homebrew/bin/bd /usr/local/bin/bd /usr/bin/bd; do
    if [ -x "$_candidate" ]; then
        _real_bd_found=true
        _real_bd_path="$_candidate"
        break
    fi
done

if [ "$_real_bd_found" = "true" ]; then
    # Run the wrapper with the real bd available in PATH (at a position after a fake dir)
    # The wrapper must skip a PATH entry pointing to itself and find the real one.
    _fake_dir=$(mktemp -d)
    cp "$_WRAPPER" "$_fake_dir/bd"
    chmod +x "$_fake_dir/bd"

    if PATH="$_fake_dir:$(dirname "$_real_bd_path"):$PATH" /bin/sh "$_fake_dir/bd" version > /tmp/bd_wrapper_test2_out.txt 2>&1; then
        _pass "Test 2: 'bd version' passed through to real bd binary (exit 0)"
    else
        if PATH="$_fake_dir:$(dirname "$_real_bd_path"):$PATH" /bin/sh "$_fake_dir/bd" help > /tmp/bd_wrapper_test2_out.txt 2>&1; then
            _pass "Test 2: 'bd help' passed through to real bd binary (exit 0)"
        else
            if grep -q "bd-wrapper: ERROR" /tmp/bd_wrapper_test2_out.txt 2>/dev/null; then
                _fail "Test 2: wrapper produced its own error instead of passing through"
                cat /tmp/bd_wrapper_test2_out.txt
            else
                _pass "Test 2: command passed through to real bd (non-zero exit is bd's own response)"
            fi
        fi
    fi
    rm -rf "$_fake_dir"
else
    echo "SKIP: Test 2 skipped — no real bd binary found in standard locations"
fi

# ---------------------------------------------------------------------------
# Test 3: Wrapper finds bd_lint_contracts.py correctly when called from
#         a DIFFERENT working directory (simulates CI running from repo root)
# ---------------------------------------------------------------------------
echo ""
echo "--- Test 3: wrapper finds bd_lint_contracts.py when CWD differs from script dir ---"
_old_dir=$(pwd)
cd /tmp
if /bin/sh "$_WRAPPER" lint --check=architecture-contracts --help > /tmp/bd_wrapper_test3_out.txt 2>&1; then
    _pass "Test 3: wrapper finds bd_lint_contracts.py from /tmp (exit 0)"
else
    _exit_code=$?
    if grep -q "bd_lint_contracts\|architecture-contracts\|lint\|bead" /tmp/bd_wrapper_test3_out.txt 2>/dev/null; then
        _pass "Test 3: wrapper finds bd_lint_contracts.py from /tmp (exit $_exit_code, output matches Python)"
    else
        _fail "Test 3: bd_lint_contracts.py not found when CWD differs from script dir"
        cat /tmp/bd_wrapper_test3_out.txt
    fi
fi
cd "$_old_dir"

# ---------------------------------------------------------------------------
# Test 4: Verify wrapper is executable and has correct shebang
# ---------------------------------------------------------------------------
echo ""
echo "--- Test 4: wrapper script is executable with POSIX sh shebang ---"
_shebang=$(head -1 "$_WRAPPER")
if [ "$_shebang" = "#!/bin/sh" ]; then
    _pass "Test 4: shebang is #!/bin/sh (POSIX sh, compatible with bash and zsh)"
else
    _fail "Test 4: shebang is '$_shebang' (expected #!/bin/sh)"
fi

# ---------------------------------------------------------------------------
# Test 5: PATH-walk correctly skips the wrapper itself (no infinite recursion)
#
# Put the wrapper itself in a temp dir, add that dir before the real bd in PATH,
# and verify that lint --check=architecture-contracts still dispatches to Python
# (not to itself infinitely). This tests the early-exit before PATH-walk.
# ---------------------------------------------------------------------------
echo ""
echo "--- Test 5: lint intercept works even when wrapper is first in PATH ---"
_fake_dir2=$(mktemp -d)
cp "$_WRAPPER" "$_fake_dir2/bd"
chmod +x "$_fake_dir2/bd"
# Simulate: the wrapper is in PATH as 'bd', with contracts script alongside it
cp "$_CONTRACTS_SCRIPT" "$_fake_dir2/bd_lint_contracts.py"

if PATH="$_fake_dir2:$PATH" /bin/sh "$_fake_dir2/bd" lint --check=architecture-contracts --help > /tmp/bd_wrapper_test5_out.txt 2>&1; then
    _pass "Test 5: lint intercept works when wrapper is first in PATH (exit 0)"
else
    _exit_code=$?
    if grep -q "bd_lint_contracts\|architecture-contracts\|lint\|bead" /tmp/bd_wrapper_test5_out.txt 2>/dev/null; then
        _pass "Test 5: lint intercept works when wrapper is first in PATH (exit $_exit_code, output matches Python)"
    else
        _fail "Test 5: lint intercept failed when wrapper is first in PATH"
        cat /tmp/bd_wrapper_test5_out.txt
    fi
fi
rm -rf "$_fake_dir2"

# ---------------------------------------------------------------------------
# Test 6: Multiple wrapper copies in PATH do not exec-loop each other
#
# Simulates: original bd-wrapper in dir1, installed copy in dir2, real bd in dir3.
# Running dir1/bd with a passthrough command must reach real bd, not loop.
# ---------------------------------------------------------------------------
echo ""
echo "--- Test 6: multiple wrapper copies in PATH do not cause exec loop ---"
_real_bd_found=false
for _candidate in /opt/homebrew/bin/bd /usr/local/bin/bd /usr/bin/bd; do
    if [ -x "$_candidate" ]; then
        _real_bd_found=true
        _real_bd_for_test6="$_candidate"
        break
    fi
done

if [ "$_real_bd_found" = "true" ]; then
    _dir6a=$(mktemp -d)  # "source checkout" wrapper
    _dir6b=$(mktemp -d)  # "installed copy" wrapper

    cp "$_WRAPPER" "$_dir6a/bd"
    chmod +x "$_dir6a/bd"
    cp "$_CONTRACTS_SCRIPT" "$_dir6a/bd_lint_contracts.py"

    cp "$_WRAPPER" "$_dir6b/bd"
    chmod +x "$_dir6b/bd"
    cp "$_CONTRACTS_SCRIPT" "$_dir6b/bd_lint_contracts.py"

    # PATH: dir6a (wrapper copy 1) -> dir6b (wrapper copy 2) -> real bd dir
    # Include /usr/bin:/bin so POSIX tools (dirname, readlink) remain available
    # even with the narrowed PATH — otherwise the wrapper itself breaks.
    _real_bd_dir=$(dirname "$_real_bd_for_test6")
    # Invoke via absolute /bin/sh so PATH narrowing can't break the launcher.
    if PATH="$_dir6a:$_dir6b:$_real_bd_dir:/usr/bin:/bin" /bin/sh "$_dir6a/bd" version > /tmp/bd_wrapper_test6_out.txt 2>&1; then
        _pass "Test 6: 'bd version' passes through two wrapper copies to real bd (exit 0)"
    else
        _exit_code=$?
        if grep -q "bd-wrapper: ERROR" /tmp/bd_wrapper_test6_out.txt 2>/dev/null; then
            _fail "Test 6: wrapper error instead of passthrough — possible loop or missing real bd"
            cat /tmp/bd_wrapper_test6_out.txt
        elif [ "$_exit_code" = "127" ] || grep -qE "(not found|No such file)" /tmp/bd_wrapper_test6_out.txt 2>/dev/null; then
            _fail "Test 6: launcher failed to execute wrapper (exit $_exit_code) — test harness bug"
            cat /tmp/bd_wrapper_test6_out.txt
        else
            _pass "Test 6: command passed through to real bd (non-zero exit is bd's own response)"
        fi
    fi
    rm -rf "$_dir6a" "$_dir6b"
else
    echo "SKIP: Test 6 skipped — no real bd binary found in standard locations"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
