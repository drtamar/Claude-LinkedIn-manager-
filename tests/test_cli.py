"""Tests for the CLI wiring, using a stubbed Claude client."""

from __future__ import annotations

import linkedin_manager.cli as cli
from linkedin_manager.config import Config


def _patch_client(monkeypatch, response="STUBBED"):
    """Replace the client builder so no API call happens."""

    class Stub:
        def complete(self, *, system, user, max_tokens=4000):
            return response

    monkeypatch.setattr(cli, "_build_client", lambda config: Stub())


def test_parser_requires_subcommand():
    parser = cli.build_parser()
    # argparse exits with SystemExit when a required subcommand is missing.
    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code != 0
    else:  # pragma: no cover
        raise AssertionError("expected SystemExit")


def test_post_command_writes_output(monkeypatch, tmp_path, capsys):
    _patch_client(monkeypatch, "Here is a post")
    config = Config(api_key="sk-test", output_dir=tmp_path)
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls: config))

    code = cli.main(["post", "launching a new feature", "--tone", "bold"])
    assert code == 0

    out = capsys.readouterr().out
    assert "Here is a post" in out
    # A file was saved to the output dir.
    assert list(tmp_path.glob("post-*.txt"))


def test_read_input_long_literal_does_not_crash():
    # A string longer than any filesystem path limit must be treated as
    # literal text, not probed as a file path (would raise OSError).
    long_text = "x" * 5000
    assert cli._read_input(long_text) == long_text


def test_read_input_reads_existing_file(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("from a file", encoding="utf-8")
    assert cli._read_input(str(f)) == "from a file"


def test_save_failure_raises_runtime_error(tmp_path):
    from linkedin_manager.config import Config

    # Point the output dir at a path whose parent is a file, so mkdir fails.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    config = Config(api_key="sk-test", output_dir=blocker / "sub")
    import pytest

    with pytest.raises(RuntimeError, match="Failed to save output"):
        cli._save(config, "post", "hello")


def test_upsert_env_creates_and_updates(tmp_path):
    env = tmp_path / ".env"
    cli.upsert_env(env, {"LINKEDIN_ACCESS_TOKEN": "tok1"})
    assert "LINKEDIN_ACCESS_TOKEN=tok1" in env.read_text()

    # Existing key is replaced in place; a new key is appended.
    cli.upsert_env(
        env, {"LINKEDIN_ACCESS_TOKEN": "tok2", "LINKEDIN_AUTHOR_URN": "urn:li:person:1"}
    )
    text = env.read_text()
    assert "LINKEDIN_ACCESS_TOKEN=tok2" in text
    assert "tok1" not in text
    assert "LINKEDIN_AUTHOR_URN=urn:li:person:1" in text


def test_upsert_env_preserves_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-keep\n", encoding="utf-8")
    cli.upsert_env(env, {"LINKEDIN_AUTHOR_URN": "urn:li:person:9"})
    text = env.read_text()
    assert "ANTHROPIC_API_KEY=sk-keep" in text
    assert "LINKEDIN_AUTHOR_URN=urn:li:person:9" in text


def test_cv_command_runs(monkeypatch, tmp_path, capsys):
    _patch_client(monkeypatch, "# CV\n...")
    config = Config(api_key="sk-test", output_dir=tmp_path)
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls: config))

    code = cli.main(["cv", "5 years as a designer", "--role", "Design Lead"])
    assert code == 0
    assert list(tmp_path.glob("cv-*.md"))
