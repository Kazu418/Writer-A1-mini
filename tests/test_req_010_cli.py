import json
from plotnote.cli import main


def test_doctor(capsys):
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["offline_ready"]


def test_end_to_end(make_pdf, profile, tmp_path):
    pdf = make_pdf()
    out = tmp_path / "converted"
    assert main(["inspect", str(pdf)]) == 0
    assert main(["convert", str(pdf), "-o", str(out)]) == 0
    p = tmp_path / "profile.json"
    profile.save(p)
    export = tmp_path / "export"
    assert (
        main(
            [
                "export",
                str(out / "page-001.svg"),
                "--profile",
                str(p),
                "--homed",
                "--air-mm",
                "5",
                "-o",
                str(export),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "validate",
                str(export / "page-001.gcode.3mf"),
                "--profile",
                str(export / "effective-profile.json"),
            ]
        )
        == 0
    )


def test_errors(tmp_path):
    assert (
        main(["convert", str(tmp_path / "missing.pdf"), "-o", str(tmp_path / "out")])
        == 2
    )
    assert main(["fonts", "--check", "😀"]) == 2
