"""Reject stale/modified provider sources before building the dependency wheel."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('core_bootstrap', ROOT / 'scripts/install-core-candidate.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def test_dependency_bootstrap_rejects_stale_and_modified_source(tmp_path):
    source = tmp_path / 'core'
    source.mkdir()
    manifest = source / 'pyproject.toml'
    original = '[project]\nname="townlight-core"\nversion="1.3.0.dev2"\n'
    manifest.write_text(original)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=source, text=True).strip()
    git('init')
    git('add', 'pyproject.toml')
    git('-c', 'user.name=Townlight synthetic fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-m', 'Synthetic provider fixture')
    pin = {'commit': git('rev-parse', 'HEAD'), 'distribution': 'townlight-core', 'version': '1.3.0.dev2'}
    bootstrap.validate_source(source, pin)
    with pytest.raises(ValueError, match='commit mismatch'):
        bootstrap.validate_source(source, {**pin, 'commit': '0' * 40})
    manifest.write_text(original + '# changed after pin\n')
    with pytest.raises(ValueError, match='modified tracked files'):
        bootstrap.validate_source(source, pin)
    manifest.write_text(original)
    with pytest.raises(ValueError, match='metadata differs'):
        bootstrap.validate_source(source, {**pin, 'version': '1.2.1'})
