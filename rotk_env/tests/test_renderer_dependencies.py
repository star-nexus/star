"""Renderer dependency boundaries must hold in a fresh interpreter."""
import subprocess
import sys

import pytest

pytest.importorskip('star_native')


@pytest.mark.parametrize('renderer', ['web', 'pygame'])
def test_selected_renderer_does_not_import_other_engine(renderer):
    subprocess.run([sys.executable, '-m', 'rotk_env.tests.renderer_dependency_probe',
                    renderer], check=True, timeout=30)
