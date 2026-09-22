# Agent Quality Gates

Mandatory structure for all Claude Code agents. Based on Adrian's Quality Gate pattern: every agent declares what it checks before acting, what it owns, how it verifies, and what mistakes it avoids.

## Why

Agents without explicit boundaries drift in scope, skip verification, and repeat known mistakes. The 4 quality gate sections make each agent self-documenting and self-correcting.

## The 4 Mandatory Sections

### 1. Pre-flight Checklist

Questions/checks the agent MUST verify BEFORE taking action.

```markdown
## Pre-flight Checklist

- [ ] Is the target file under version control?
- [ ] Are tests currently passing?
- [ ] Has the relevant context (ticket, spec, code) been read?
```

**Purpose:** Prevents "act first, ask later" failures. Forces the agent to gather context.

### 2. Responsibility

Clear scope boundaries: what this agent owns and what it does NOT.

```markdown
## Responsibility

| Owns | Does NOT Own |
|------|-------------|
| Writing unit tests | Modifying production code |
| Reporting test results | Deploying changes |
```

**Purpose:** Prevents scope creep. Agents that know their boundaries make better handoff decisions.

### 3. VERIFY

Concrete shell commands the agent runs to verify its work before reporting success.

```markdown
## VERIFY

```bash
# Run test suite
uv run pytest tests/ -x

# Validate agent structure
python3 scripts/validate-agent.py .claude/agents/my-agent/
```
```

**Purpose:** No agent should report "done" without running verification. This makes the verification step explicit and reproducible.

### 4. LEARN

Documented anti-patterns and mistakes this agent type should avoid.

```markdown
## LEARN

- **Never mock the function under test**: If the test passes after deleting the function, you're testing the mock
- **Don't expand scope beyond the ticket**: Review only what was asked
- **Don't report success without verification**: Always run VERIFY commands first
```

**Purpose:** Encodes team knowledge. Each mistake is documented once, then prevented forever.

## Validation

Validate agent structure including quality gates:

```bash
# Warnings only (default)
python3 meta/skills/agent-forge/scripts/validate-agent.py .claude/agents/my-agent/

# Strict mode (quality gate sections are errors)
python3 meta/skills/agent-forge/scripts/validate-agent.py --strict .claude/agents/my-agent/
```

## Reference Implementations

These agents have been updated with all 4 sections:

- `agents/plan-reviewer.md` -- Read-only plan challenge advisor
- `agents/home/prompt.md` -- Infrastructure agent (split format)

## Integration with Software Factory

Each specialized agent in the factory has clear boundaries:
1. **Pre-flight** ensures prerequisites are met before work starts
2. **Responsibility** defines handoff points between agents in a pipeline
3. **VERIFY** provides the quality gate that must pass before the next stage
4. **LEARN** accumulates institutional knowledge across sessions
