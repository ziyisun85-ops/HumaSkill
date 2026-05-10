# HumaSkill — Agent Assignments

## Recommended Division of Labor

| Agent | Tasks | Rationale |
|---|---|---|
| **Claude Code** | Task 01, Task 05, Task 06 | Best suited for project skeleton creation, complex backend/policy/executor integration, and final wiring (main entry, logging, README). Strong at generating consistent boilerplate and integration code. |
| **DeepSeek TUI** | Task 02, Task 03, Task 04 | Best suited for modular implementations: exceptions, I/O utils, skill registry, rule-based composer, validator, and transition manager. These are self-contained units with clear interfaces. |
| **Codex CLI** | Local test execution, import cleanup, small bug fixes, fix failing tests | Secondary role: runs tests locally, cleans up imports, fixes small bugs that slip through, patches failing test cases. Not responsible for new feature implementation. |
| **Codex App** | Final review: interface consistency audit, hidden bug detection, minimal targeted fixes | Runs the final review pass against INTERFACES.md, checks interface consistency, detects edge cases, and applies minimal targeted patches. |
| **Hermes** | Project manager, interface gatekeeper, acceptance inspector, final orchestrator | Maintains INTERFACES.md consistency, checks that agents only edit allowed files, runs acceptance tests, coordinates agent handoffs. |

---

## Role Descriptions

### Claude Code
Claude Code handles project skeleton, complex integration, backend implementation, policy interfaces, executor, and main entry point. These tasks require generating consistent structure across many files and connecting modules together — areas where Claude Code excels.

### DeepSeek TUI
DeepSeek TUI handles modular, self-contained implementations: utils, skill registry, rule-based composer, validator, and transition manager. Each task has clear interfaces and well-defined test expectations, making them ideal for focused implementation.

### Codex CLI
Codex CLI is the tactical fixer: runs `pytest` to find failures, cleans up import issues, fixes small bugs, and patches edge cases. It operates after the main tasks are complete and does not implement new features.

### Codex App
Codex App performs the final review: audits the complete codebase against INTERFACES.md, checks for interface inconsistencies, detects hidden bugs, and applies minimal targeted fixes. It produces a structured review report with critical issues, interface gaps, test gaps, and a recommended patch plan.

### Hermes
Hermes is the project manager and interface gatekeeper:
- Maintains consistency of INTERFACES.md as the single source of truth
- Verifies each agent only edits files allowed by their task
- Runs acceptance checks after each task
- Coordinates handoffs between agents
- Performs final acceptance validation

---

## Agent Handoff Protocol

1. Each agent reads `PROJECT_PLAN.md`, `INTERFACES.md`, `TASKS.md`, and `ACCEPTANCE_CHECKLIST.md` before starting
2. Each agent edits ONLY the files explicitly listed in their task
3. After completing a task, the agent runs its task-specific tests
4. Hermes reviews the output before authorizing the next task
5. If an agent discovers an interface issue, it reports to Hermes — does NOT modify INTERFACES.md
