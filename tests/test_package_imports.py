from marketgame import __all__
from marketgame.__main__ import main
from marketgame.app import create_app


def test_package_imports() -> None:
    assert isinstance(__all__, list)


def test_module_entrypoint_exports_main() -> None:
    assert callable(main)


def test_app_factory_is_callable() -> None:
    assert callable(create_app)
