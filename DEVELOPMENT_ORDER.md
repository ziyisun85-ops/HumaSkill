# HumaSkill — Development Order

## Recommended Execution Order

```
 1. agent_prompts/01_skeleton_prompt.md      → Claude Code
 2. agent_prompts/02_skills_registry_prompt.md → DeepSeek TUI
 3. agent_prompts/03_composer_prompt.md       → DeepSeek TUI
 4. agent_prompts/04_transition_prompt.md     → DeepSeek TUI
 5. agent_prompts/05_backend_executor_prompt.md → Claude Code
 6. agent_prompts/06_main_readme_testfix_prompt.md → Claude Code
 7. Codex CLI: local fix pass                 → Codex CLI
 8. agent_prompts/07_codex_app_final_review_prompt.md → Codex App
 9. Hermes: final acceptance                  → Hermes
```

---

## Dependency Rationale

1. **01 Skeleton** must run first — creates the project structure all other tasks build on
2. **02 Skills Registry** runs early — SkillInfo and SkillRegistry are dependencies for Composer, TransitionManager, and Executor
3. **03 Composer** depends on Skills Registry (needs skill names)
4. **04 Transition** depends on Skills Registry (needs pose/risk info for repair rules)
5. **05 Backend/Executor** depends on Skills Registry and TransitionManager (executes repaired sequences)
6. **06 Main/Logging** depends on all previous tasks (wires everything together)
7. **Codex CLI** runs after all implementation tasks — fixes test failures and import issues
8. **Codex App** runs final review — audits complete codebase
9. **Hermes** runs acceptance after all other agents are done

---

## Pre-Task Requirements

Every subagent MUST read before starting:
- `PROJECT_PLAN.md`
- `INTERFACES.md`
- `TASKS.md`
- `ACCEPTANCE_CHECKLIST.md`

Every subagent MUST:
- Only edit files explicitly allowed in their task prompt
- Follow INTERFACES.md strictly
- Run their task-specific tests before declaring completion

---

## Parallelization Notes

- Tasks 02, 03, 04 (all DeepSeek TUI) can potentially run in parallel since they touch separate modules, but sequential execution is recommended due to dependency ordering
- Task 01 MUST complete before any other task
- Task 05 can start in parallel with Tasks 03-04 only after Task 02 completes (skill registry dependency)
- Task 06 must run after all implementation tasks
