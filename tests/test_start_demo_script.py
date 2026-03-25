from pathlib import Path


def test_start_demo_script_avoids_powershell_host_automatic_variable() -> None:
    script = Path("scripts/start_demo.ps1").read_text(encoding="utf-8")

    assert "[string]$BindHost" in script
    assert '[string]$Host = "127.0.0.1"' not in script
