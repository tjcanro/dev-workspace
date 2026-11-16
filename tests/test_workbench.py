import runpy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import tomllib
import unittest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = runpy.run_path(str(ROOT / "bin" / "workbench"))


class WorkbenchTests(unittest.TestCase):
    def test_every_role_generates_valid_codex_toml(self):
        roles = WORKBENCH["discover_roles"]([ROOT])
        self.assertIn("code-reviewer", roles)
        for path in roles.values():
            document = tomllib.loads(WORKBENCH["codex_agent_text"](path))
            self.assertTrue(document["name"])
            self.assertTrue(document["description"])
            self.assertTrue(document["developer_instructions"])

    def test_code_reviewer_is_read_only_in_codex(self):
        text = WORKBENCH["codex_agent_text"](ROOT / "agents" / "roles" / "code-reviewer.md")
        document = tomllib.loads(text)
        self.assertEqual(document["sandbox_mode"], "read-only")

    def test_tmuxp_templates_render_without_placeholders(self):
        profile = WORKBENCH["load_toml"](ROOT / "profiles" / "example.toml")
        for name in ("local-dev.yaml.tmpl", "remote-dev.yaml.tmpl"):
            rendered = WORKBENCH["render_template"](ROOT / "tmuxp" / name, profile)
            self.assertNotIn("${", rendered)
            self.assertIn("session_name:", rendered)
            document = yaml.safe_load(rendered)
            self.assertTrue(document["session_name"])
            self.assertTrue(document["windows"])

    def test_public_profile_has_no_enabled_remote(self):
        profile = WORKBENCH["load_toml"](ROOT / "profiles" / "example.toml")
        self.assertFalse(profile["remote"]["enabled"])

    def test_external_skill_uses_frontmatter_name(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / "knowledge-repository"
            external.mkdir()
            (external / "SKILL.md").write_text(
                "---\n"
                "name: rust-skills\n"
                "description: Apply Rust knowledge.\n"
                "---\n\n"
                "# Rust skills\n\n"
                "Use the repository knowledge.\n",
                encoding="utf-8",
            )

            skills = WORKBENCH["discover_skills"]([ROOT], [external])

            self.assertEqual(skills["rust-skills"], external)

    def test_agent_scaffold_creates_a_valid_role_and_skill(self):
        function_globals = WORKBENCH["new_agent"].__globals__
        original_root = function_globals["ROOT"]
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            (temporary_root / "agents" / "roles").mkdir(parents=True)
            (temporary_root / "skills").mkdir()
            function_globals["ROOT"] = temporary_root
            try:
                WORKBENCH["new_agent"](
                    SimpleNamespace(
                        name="test-specialist",
                        description="Inspect test failures without changing source files",
                        read_only=True,
                        with_skill=True,
                    )
                )
                role = temporary_root / "agents" / "roles" / "test-specialist.md"
                skill = temporary_root / "skills" / "test-specialist" / "SKILL.md"
                role_metadata, _ = WORKBENCH["parse_frontmatter"](role)
                skill_metadata, _ = WORKBENCH["parse_frontmatter"](skill)
                self.assertEqual(role_metadata["name"], "test-specialist")
                self.assertEqual(role_metadata["permissionMode"], "plan")
                self.assertEqual(skill_metadata["name"], "test-specialist")
                tomllib.loads(WORKBENCH["codex_agent_text"](role))
            finally:
                function_globals["ROOT"] = original_root


if __name__ == "__main__":
    unittest.main()
