"""Build workspaces obey the same four-layer boundary as runtime source."""
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]
LAYERS = {"framework", "protocol", "rotk_env", "rotk_agent"}


def read_toml(path):
    return tomllib.loads(path.read_text())


def test_build_workspaces_stay_inside_the_four_source_layers():
    cargo = read_toml(ROOT / "Cargo.toml")
    project = read_toml(ROOT / "pyproject.toml")
    members = cargo["workspace"]["members"] + project["tool"]["uv"]["workspace"]["members"]
    assert not (ROOT / "native").exists(), "A backend must not become a fifth source layer"
    for member in members:
        path = (ROOT / member).resolve()
        assert path.relative_to(ROOT).parts[0] in LAYERS, member
        assert path.is_dir(), member

    # Reusable framework crates cannot depend on a concrete ENV or Agent.
    shared = cargo["workspace"].get("dependencies", {})
    for member in cargo["workspace"]["members"]:
        path = ROOT / member
        if path.relative_to(ROOT).parts[0] != "framework":
            continue
        manifest = read_toml(path / "Cargo.toml")
        sections = [manifest]
        sections.extend(manifest.get("target", {}).values())
        for section in sections:
            for kind in ("dependencies", "build-dependencies", "dev-dependencies"):
                for name, dependency in section.get(kind, {}).items():
                    if not isinstance(dependency, dict):
                        continue
                    owner = path
                    if dependency.get("workspace"):
                        dependency = shared[name]
                        owner = ROOT
                    if isinstance(dependency, dict) and "path" in dependency:
                        target = (owner / dependency["path"]).resolve()
                        assert target.relative_to(ROOT).parts[0] == "framework", (member, name)


def test_extension_build_cache_tracks_both_framework_and_env_sources():
    cargo = read_toml(ROOT / "Cargo.toml")
    project = read_toml(ROOT / "pyproject.toml")
    for member in project["tool"]["uv"]["workspace"]["members"]:
        path = ROOT / member
        manifest = read_toml(path / "pyproject.toml")
        if manifest.get("build-system", {}).get("build-backend") != "maturin":
            continue
        covered = {p.resolve() for key in manifest["tool"]["uv"]["cache-keys"]
                   if "file" in key for p in path.glob(key["file"])}
        required = {ROOT / "Cargo.toml", ROOT / "Cargo.lock", path / "pyproject.toml"}
        for crate in cargo["workspace"]["members"]:
            required.add(ROOT / crate / "Cargo.toml")
            required.update((ROOT / crate / "src").rglob("*.rs"))
        assert {p.resolve() for p in required} <= covered, sorted(
            str(p.relative_to(ROOT)) for p in required if p.resolve() not in covered)
