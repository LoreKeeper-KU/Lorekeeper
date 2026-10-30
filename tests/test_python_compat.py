import ast
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "continuity_checker"
PYTHON_311_ONLY = ["StrEnum", "tomllib", "ExceptionGroup", "typing import Self"]


def test_package_avoids_python_311_only_features():
    """Static check only: the project must stay importable on Python 3.10."""
    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf8")
        ast.parse(source, feature_version=(3, 10))
        for name in PYTHON_311_ONLY:
            assert name not in source, f"{path.name} uses {name} (Python 3.11+)"
