#!/usr/bin/env python3
"""Standalone script to validate all skills in configs/skills.yaml.

Usage:
    python scripts/validate_skills.py

Exits with code 0 if all skills are valid, non-zero otherwise.
"""

import sys
from pathlib import Path


def main():
    """Load skills.yaml and validate every skill. Print results."""
    # Discover the project root (parent of the scripts directory)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    skills_yaml_path = project_root / "configs" / "skills.yaml"

    # Add project root to sys.path so humaskill imports work
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from humaskill.utils.io import load_yaml
    from humaskill.skills.skill_schema import validate_skill
    from humaskill.utils.errors import InvalidSkillConfigError
    from humaskill.utils.printing import print_section, print_info, print_error

    print_section("HumaSkill — Skill Configuration Validator")

    if not skills_yaml_path.exists():
        print_error(f"Skills YAML file not found: {skills_yaml_path}")
        sys.exit(1)

    print_info(f"Loading skills from: {skills_yaml_path}")

    try:
        raw_skills = load_yaml(str(skills_yaml_path))
    except Exception as e:
        print_error(f"Failed to load YAML: {e}")
        sys.exit(1)

    if raw_skills is None:
        print_error("Skills YAML is empty or null.")
        sys.exit(1)

    if not isinstance(raw_skills, list):
        print_error("Skills YAML must contain a list of skill definitions.")
        sys.exit(1)

    total = len(raw_skills)
    passed = 0
    failed = 0

    for raw in raw_skills:
        skill_name = raw.get("name", "<unknown>")
        try:
            validate_skill(raw)
            print_info(f"OK  — {skill_name}")
            passed += 1
        except InvalidSkillConfigError as e:
            print_error(f"FAIL — {skill_name}: {e}")
            failed += 1
        except Exception as e:
            print_error(f"FAIL — {skill_name}: unexpected error: {e}")
            failed += 1

    print_section("Validation Summary")
    print_info(f"Total skills: {total}")
    print_info(f"Passed:       {passed}")
    if failed > 0:
        print_error(f"Failed:       {failed}")
    else:
        print_info("Failed:       0")

    if failed > 0:
        sys.exit(1)
    else:
        print_info("All skills valid.")
        sys.exit(0)


if __name__ == "__main__":
    main()
