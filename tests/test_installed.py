"""Exercise the package through normal defaults in an isolated installation."""

from __future__ import annotations

lazy import asyncio
lazy import os
lazy from pathlib import Path

PUBLISHED = (
    "bazaar-compute-node~=0.3.0rc14",
    "bazaar-contrib-agent~=0.3.0rc14",
    "bazaar-contrib-collaboration~=0.3.0rc14",
    "bazaar-contrib-messages-node~=0.3.0rc14",
    "bazaar-contrib-reminder~=0.3.0rc14",
    "pytest",
    "pytest-asyncio",
    "blockbuster>=1.5.29,<1.6",
)


async def test_installed_legacy_node_migrations_uses_default_configuration(
    tmp_path: Path,
):
    root = (await asyncio.to_thread(Path(__file__).resolve)).parents[1]
    output = tmp_path / "distributions"
    environment = dict(os.environ) | {
        "BCN_HOME": str(tmp_path / "home"),
        "UV_TOOL_DIR": str(tmp_path / "tools"),
        "UV_TOOL_BIN_DIR": str(tmp_path / "bin"),
        "UV_CACHE_DIR": str(tmp_path / "cache"),
    }
    process = await asyncio.create_subprocess_exec(
        "uv",
        "build",
        str(root),
        "--no-sources",
        "--out-dir",
        str(output),
        cwd=tmp_path,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    assert process.returncode == 0, stdout.decode()
    tests = Path(__file__).with_name("migration_cases.py")
    for suffix in ("*.whl", "*.tar.gz"):
        command = [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--python",
            "3.15",
            "--prerelease",
            "allow",
        ]
        for artifact in await asyncio.to_thread(list, output.glob(suffix)):
            command.extend(["--with", str(artifact)])
        for requirement in PUBLISHED:
            command.extend(["--with", requirement])
        command.extend(
            [
                str(Path(__file__).with_name("run_installed.py")),
                str(output),
                str(root / "scripts/ci_pytest.py"),
                "-c",
                str(root / "pyproject.toml"),
                "--confcutdir",
                str(tests.parent),
                "-q",
                str(tests),
            ]
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=tmp_path,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await process.communicate()
        assert process.returncode == 0, stdout.decode()
