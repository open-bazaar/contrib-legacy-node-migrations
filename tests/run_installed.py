"""Restore default dependencies while testing the locally built distributions."""

import importlib.metadata
import json
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from tempfile import TemporaryDirectory

import tomli_w
from bazaar_compute_node.boot import defaults
from packaging.requirements import Requirement
from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)

artifacts = Path(sys.argv[1])
packages: dict[str, list[Path]] = {}
for artifact in artifacts.iterdir():
    if artifact.suffix == ".whl":
        name, *_ = parse_wheel_filename(artifact.name)
    elif artifact.name.endswith(".tar.gz"):
        name, _ = parse_sdist_filename(artifact.name)
    else:
        continue
    packages.setdefault(str(name), []).append(artifact)
for name, distributions in packages.items():
    index = artifacts / "simple" / name
    index.mkdir(parents=True, exist_ok=True)
    (index / "index.html").write_text(
        "\n".join(
            f'<a href="{path.as_uri()}">{path.name}</a>' for path in distributions
        )
    )
source = (artifacts / "simple").as_uri()
document = defaults()
for package in document["contribs"]:
    package["source"] = (
        source
        if Requirement(package["package"]).name in packages
        else "https://pypi.org/simple"
    )
defaults = {Requirement(package["package"]).name for package in document["contribs"]}
for name in packages.keys() - defaults - {"bazaar-compute-node", "bazaar-core"}:
    direct = distribution(name).read_text("direct_url.json")
    assert direct is not None
    artifact = json.loads(direct)["url"]
    document["contribs"].append({"package": f"{name} @ {artifact}"})
for name in ("blockbuster", "pytest", "pytest-asyncio"):
    try:
        installed = distribution(name)
    except PackageNotFoundError:
        continue
    document["contribs"].append(
        {"package": f"{name}=={installed.version}", "source": "https://pypi.org/simple"}
    )
config = Path(os.environ["BCN_HOME"]) / ".bcn" / "config.toml"
config.parent.mkdir(parents=True, exist_ok=True)
config.write_text(tomli_w.dumps(document))
# uv run --with keeps these distributions in a layer that a later uv pip install into
# this interpreter cannot see, so it would install the released copies over them.
requirements: dict[str, str] = {}
for installed in importlib.metadata.distributions():
    name = canonicalize_name(installed.metadata["Name"])
    direct = installed.read_text("direct_url.json")
    requirements.setdefault(
        name,
        f"{name} @ {json.loads(direct)['url']}"
        if direct is not None
        else f"{name}=={installed.version}",
    )
with TemporaryDirectory(prefix="bcn-installed-") as directory:
    environment = Path(directory)
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(environment)], check=True
    )
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), *requirements.values()],
        check=True,
    )
    variables = os.environ | {
        "PATH": str(python.parent) + os.pathsep + os.environ.get("PATH", "")
    }
    subprocess.run(
        [str(python), "-m", "bazaar_compute_node", "--help"], check=True, env=variables
    )
    subprocess.run([str(python), *sys.argv[2:]], check=True, env=variables)
