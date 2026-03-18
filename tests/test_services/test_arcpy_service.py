"""Tests for ArcPyService."""
import pytest
from src.services.arcpy_service import ArcPyService
from src.core.exceptions import ArcPyExecutionError


class FakeArcPy:
    """Minimal ArcPy stand-in for unit tests."""

    class env:
        workspace = None

    added_fields: list = []
    calculated_fields: list = []
    copied_features: list = []

    @classmethod
    def AddField_management(cls, **kwargs):
        cls.added_fields.append(kwargs)

    @classmethod
    def CalculateField_management(cls, **kwargs):
        cls.calculated_fields.append(kwargs)

    @classmethod
    def CopyFeatures_management(cls, **kwargs):
        cls.copied_features.append(kwargs)


def test_add_fields_success(monkeypatch):
    """add_fields calls AddField_management for each field."""
    fake = FakeArcPy()
    fake.added_fields = []
    svc = ArcPyService(workspace="C:/test.gdb")
    monkeypatch.setattr(svc, "_arcpy", lambda: fake)

    fields = [
        {"name": "ROAD_WIDTH", "type": "DOUBLE"},
        {"name": "SURFACE_TYPE", "type": "TEXT", "length": 50},
    ]
    svc.add_fields("ROADS", fields)

    assert len(fake.added_fields) == 2
    assert fake.added_fields[0]["field_name"] == "ROAD_WIDTH"
    assert "field_length" not in fake.added_fields[0]
    assert fake.added_fields[1]["field_length"] == 50


def test_add_fields_raises_on_arcpy_failure(monkeypatch):
    """add_fields raises ArcPyExecutionError when ArcPy fails."""

    class BrokenArcPy:
        class env:
            workspace = None

        def AddField_management(self, **kwargs):
            raise RuntimeError("simulated ArcPy error")

    svc = ArcPyService(workspace="C:/test.gdb")
    monkeypatch.setattr(svc, "_arcpy", lambda: BrokenArcPy())

    with pytest.raises(ArcPyExecutionError):
        svc.add_fields("ROADS", [{"name": "F", "type": "TEXT"}])


def test_calculate_field_success(monkeypatch):
    """calculate_field calls CalculateField_management."""
    fake = FakeArcPy()
    fake.calculated_fields = []
    svc = ArcPyService(workspace="C:/test.gdb")
    monkeypatch.setattr(svc, "_arcpy", lambda: fake)

    svc.calculate_field("ROADS", "ROAD_WIDTH", "100")

    assert len(fake.calculated_fields) == 1
    assert fake.calculated_fields[0]["field"] == "ROAD_WIDTH"
    assert fake.calculated_fields[0]["expression"] == "100"
