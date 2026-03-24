from marketgame import __all__


def test_package_imports() -> None:
    assert isinstance(__all__, list)
