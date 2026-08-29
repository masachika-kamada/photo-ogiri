from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def test_architecture_svg_and_icon_sources_are_valid_xml() -> None:
    ET.parse(ROOT / "docs" / "architecture.svg")
    for icon in (ROOT / "docs" / "icons" / "azure").glob("*.svg"):
        ET.parse(icon)


def test_architecture_uses_resource_icons_and_storage_child_names() -> None:
    source = (ROOT / "scripts" / "generate_architecture_diagram.py").read_text(
        encoding="utf-8"
    )

    assert 'icon="container-app.svg"' in source
    assert 'icon="container-apps.svg"' not in source
    assert 'image(root, "storage-account.svg"' in source
    assert "submissions / Blob Container" in source
    assert "score-jobs / Queue" in source
