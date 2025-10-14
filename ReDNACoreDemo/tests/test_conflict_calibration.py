import importlib
from pathlib import Path

import pytest


@pytest.fixture
def calibration_module(tmp_path, monkeypatch):
    module = importlib.import_module('ReDNACoreDemo.core.conflict.calibration')
    importlib.reload(module)
    temp_file = tmp_path / 'self_report_calibration.json'
    monkeypatch.setattr(module, 'CALIBRATION_PATH', temp_file, raising=False)
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    return module


def test_calibration_adjusts_weight(calibration_module):
    CalibrationManager = calibration_module.CalibrationManager
    manager = CalibrationManager()

    base = manager.get_weight('TEST', 'SkillDNA.path')
    assert 0.2 <= base <= 0.7

    manager.record_outcome('TEST', 'SkillDNA.path', 'confirmed')
    higher = manager.get_weight('TEST', 'SkillDNA.path')
    assert higher >= base

    manager.record_outcome('TEST', 'SkillDNA.path', 'contradicted')
    reduced = manager.get_weight('TEST', 'SkillDNA.path')
    assert reduced <= higher

