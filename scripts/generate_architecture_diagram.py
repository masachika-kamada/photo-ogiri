from __future__ import annotations

import base64
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ICONS = DOCS / "icons" / "azure"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def svg_data(name: str) -> str:
    content = (ICONS / name).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(content).decode("ascii")


def add(parent: ET.Element, tag: str, **attributes: object) -> ET.Element:
    normalized = {
        (key[:-1] if key.endswith("_") else key).replace("_", "-"): str(value)
        for key, value in attributes.items()
    }
    return ET.SubElement(parent, f"{{{SVG_NS}}}{tag}", normalized)


def text(parent: ET.Element, value: str, x: float, y: float, css_class: str) -> None:
    element = add(parent, "text", x=x, y=y, class_=css_class)
    element.text = value


def image(parent: ET.Element, name: str, x: float, y: float, size: float) -> None:
    add(parent, "image", href=svg_data(name), x=x, y=y, width=size, height=size)


def card(
    root: ET.Element,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    icon: str,
    title: str,
    service: str,
    detail: str,
) -> None:
    group = add(root, "g")
    add(
        group,
        "rect",
        x=x,
        y=y,
        width=width,
        height=height,
        rx=10,
        class_="card",
    )
    icon_size = 68
    image(group, icon, x + (width - icon_size) / 2, y + 28, icon_size)
    center = x + width / 2
    text(group, title, center, y + 126, "node-title")
    text(group, service, center, y + 153, "node-service")
    text(group, detail, center, y + 180, "node-detail")


def build_svg() -> None:
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": "1120",
            "height": "700",
            "viewBox": "0 0 1120 700",
            "role": "img",
            "aria-labelledby": "title description",
        },
    )
    title = add(root, "title", id="title")
    title.text = "AI審査員フォト大喜利のAzure実行時アーキテクチャ"
    description = add(root, "desc", id="description")
    description.text = (
        "ブラウザー、Container Apps、Storage Account、PostgreSQL間の非同期採点フロー"
    )
    defs = add(root, "defs")
    marker = add(
        defs,
        "marker",
        id="arrow",
        markerUnits="userSpaceOnUse",
        markerWidth=10,
        markerHeight=10,
        viewBox="0 0 10 10",
        refX=9,
        refY=5,
        orient="auto",
    )
    add(marker, "path", d="M1 1L9 5L1 9Z", fill="#344054")
    async_marker = add(
        defs,
        "marker",
        id="async-arrow",
        markerUnits="userSpaceOnUse",
        markerWidth=10,
        markerHeight=10,
        viewBox="0 0 10 10",
        refX=9,
        refY=5,
        orient="auto",
    )
    add(async_marker, "path", d="M1 1L9 5L1 9Z", fill="#d97706")
    style = add(defs, "style")
    style.text = """
      text{font-family:'Yu Gothic UI','Noto Sans JP',sans-serif;fill:#172033}
      .title{font-size:34px;font-weight:700}.subtitle{font-size:17px;fill:#52606d}
      .boundary{fill:#f8fbff;stroke:#8aa9c7;stroke-width:2;stroke-dasharray:8 8}
      .boundary-label{font-size:15px;font-weight:700;fill:#0078d4;letter-spacing:.5px}
      .card{fill:#fff;stroke:#d2dae5;stroke-width:1.5}
      .storage{fill:#f7fbff;stroke:#65a9d8;stroke-width:2}
    .node-title{font-size:20px;font-weight:700;text-anchor:middle}
    .node-service{font-size:15px;font-weight:700;fill:#475467;text-anchor:middle}
    .node-detail{font-size:14px;fill:#667085;text-anchor:middle}
    .storage-title{font-size:18px;font-weight:700;fill:#344054;text-anchor:middle}
    .storage-note{font-size:14px;fill:#667085;text-anchor:middle}
      .flow{fill:none;stroke:#344054;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;marker-end:url(#arrow)}
      .async{fill:none;stroke:#d97706;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;marker-end:url(#async-arrow)}
      .flow-label{font-size:13px;font-weight:700;fill:#475467;text-anchor:middle}
    .legend{font-size:14px;fill:#667085}
    """

    add(root, "rect", width=1120, height=700, fill="#ffffff")

    add(root, "rect", x=170, y=30, width=910, height=590, rx=16, class_="boundary")
    add(root, "rect", x=194, y=16, width=194, height=28, rx=5, fill="#ffffff")
    text(root, "AZURE RESOURCE GROUP", 208, 38, "boundary-label")

    image(root, "browser.svg", 48, 220, 76)
    text(root, "参加者 / ホスト", 86, 321, "node-title")
    text(root, "Web browser", 86, 348, "node-detail")

    card(
        root,
        x=230,
        y=150,
        width=190,
        height=220,
        icon="container-app.svg",
        title="API",
        service="Azure Container Apps",
        detail="React SPA + FastAPI",
    )

    add(root, "rect", x=500, y=90, width=270, height=330, rx=12, class_="storage")
    image(root, "storage-account.svg", 540, 106, 34)
    text(root, "Storage Account", 660, 129, "storage-title")
    image(root, "blob-container.svg", 602, 157, 62)
    text(root, "提出画像", 635, 238, "node-title")
    text(root, "submissions / Blob Container", 635, 263, "node-detail")
    image(root, "storage-queue.svg", 602, 297, 62)
    text(root, "採点ジョブ", 635, 378, "node-title")
    text(root, "score-jobs / Queue", 635, 403, "node-detail")

    card(
        root,
        x=830,
        y=150,
        width=190,
        height=220,
        icon="container-app.svg",
        title="Scoring Worker",
        service="Azure Container Apps",
        detail="SigLIP 2 / CPU",
    )
    add(root, "rect", x=600, y=480, width=340, height=110, rx=10, class_="card")
    image(root, "postgresql.svg", 625, 503, 64)
    text(root, "共有状態ストア", 810, 515, "node-title")
    text(root, "Azure Database for PostgreSQL", 810, 545, "node-service")
    text(root, "ゲーム状態 + 採点結果", 810, 572, "node-detail")

    add(root, "path", d="M124 258H230", class_="flow")
    add(root, "path", d="M420 188H602", class_="flow")
    add(root, "path", d="M420 328H602", class_="async")
    add(root, "path", d="M668 188H830", class_="flow")
    add(root, "path", d="M668 328H830", class_="async")
    add(root, "path", d="M325 370V455H700V480", class_="flow")
    add(root, "path", d="M925 370V455H860V480", class_="flow")

    add(root, "path", d="M270 662H318", class_="flow")
    text(root, "同期処理", 334, 667, "legend")
    add(root, "path", d="M450 662H498", class_="async")
    text(root, "非同期処理", 514, 667, "legend")

    ET.indent(root, space="  ")
    (DOCS / "architecture.svg").write_text(
        ET.tostring(root, encoding="unicode") + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_svg()
    print(f"Generated: {DOCS / 'architecture.svg'}")
