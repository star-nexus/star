# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Start the ENV from a source checkout without exposing dependency extras.

The launcher itself uses only the standard library. uv prepares the selected
ENV dependencies; the existing ENV entry point owns all runtime behaviour.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def launch_command(argv, uv):
    """Validate launcher options and preserve every ENV argument verbatim."""
    args = list(argv)
    if args[:1] == ["env"]:
        args.pop(0)
    parser = argparse.ArgumentParser(
        prog="uv run starbench.py",
        description="Start STARBench's RoTK environment. Defaults to Rust.",
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Start here:
  uv run starbench.py --no-hub       Explore offline; no Hub or API key needed
  uv run starbench.py               Open the menu for a connected benchmark
  uv run starbench.py --headless    Run without a window; still connects to Hub

ENV options are forwarded unchanged, for example:
  --env-id env_1                    Environment identity
  --hub-url URL                    Use your existing GameServer Hub
  --mode turn_based|real_time       Mode applied with --skip-start or --headless
  --players three_kingdoms          Three factions, applied when skipping menu
  --native-threads 1|2|4            Internal worker count (default: 1)

Offline AI slots are static. For a benchmark,
start GameServer, select External Agent / Hub in the menu, then connect Agents.
See README.md for setup and rotk_env/README.md for more ENV options.
""",
    )
    parser.add_argument(
        "--backend", choices=("rust", "python"), default="rust",
        help="ENV implementation (default: rust; python is an explicit fallback)",
    )
    options, _ = parser.parse_known_args(args)
    command = [uv, "run"]
    if options.backend == "rust":
        command.extend(["--extra", "native"])
    command.extend(["rotk_env/main.py", *args])
    return command


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    # Parse help/invalid backends before looking up uv or preparing dependencies.
    command = launch_command(args, "uv")
    uv = shutil.which("uv")
    if uv is None:
        print("STARBench needs uv. Install it from https://docs.astral.sh/uv/ "
              "and run this command again.", file=sys.stderr)
        return 127
    command[0] = uv
    backend = "Rust" if "--extra" in command[:4] else "Python"
    print(f"Preparing STARBench ENV ({backend}). "
          "Dependencies are prepared automatically; the first launch may take longer.",
          flush=True)
    if os.name == "posix":
        # Keep the original signal/exit behaviour, with no extra supervisor.
        os.chdir(ROOT)
        os.execv(uv, command)
    try:
        return subprocess.call(command, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
