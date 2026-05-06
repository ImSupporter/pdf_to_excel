import ast
from pathlib import Path


def test_main_does_not_import_torch_at_startup():
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))

    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name != "torch" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "torch"
