"""Smoke tests verifying the argent package structure is importable."""

import argent
import argent.budget
import argent.ingress
import argent.pipeline
import argent.security
import argent.trimmer


def test_version_string_exists() -> None:
    """Package exposes a __version__ string."""
    assert isinstance(argent.__version__, str)
    assert argent.__version__ != ""


def test_subpackages_importable() -> None:
    """All Epic subpackages import without error and are namespaced under argent."""
    for mod in (
        argent.pipeline,
        argent.ingress,
        argent.budget,
        argent.trimmer,
        argent.security,
    ):
        assert mod.__name__.startswith("argent.")
