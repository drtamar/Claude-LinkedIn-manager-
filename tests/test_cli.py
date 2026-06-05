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


def test_cv_command_runs(monkeypatch, tmp_path, capsys):
    _patch_client(monkeypatch, "# CV\n...")
    config = Config(api_key="sk-test", output_dir=tmp_path)
    monkeypatch.setattr(Config, "from_env", classmethod(lambda cls: config))

    code = cli.main(["cv", "5 years as a designer", "--role", "Design Lead"])
    assert code == 0
    assert list(tmp_path.glob("cv-*.md"))
