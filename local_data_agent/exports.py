from __future__ import annotations

import csv
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Literal

ExportFormat = Literal["csv", "xlsx", "pdf"]


def export_rows(rows: list[dict[str, Any]], export_format: ExportFormat, exports_dir: Path) -> Path:
    exports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    path = exports_dir / f"dataset-{stamp}.{export_format}"
    if export_format == "csv":
        write_csv(rows, path)
    elif export_format == "xlsx":
        write_xlsx(rows, path)
    elif export_format == "pdf":
        write_pdf(rows, path)
    else:
        raise ValueError("Formato de exportación no soportado.")
    return path


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["message"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        else:
            writer.writerow({"message": "Sin datos"})


def write_xlsx(rows: list[dict[str, Any]], path: Path) -> None:
    import pandas as pd

    pd.DataFrame(rows or [{"message": "Sin datos"}]).to_excel(path, index=False)


def write_pdf(rows: list[dict[str, Any]], path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Reporte local de datos")
    y -= 30
    pdf.setFont("Helvetica", 9)
    for index, row in enumerate(rows[:100], start=1):
        line = f"{index}. " + "; ".join(f"{key}: {value}" for key, value in row.items())
        for chunk in [line[i : i + 110] for i in range(0, len(line), 110)]:
            if y < 40:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y = height - 40
            pdf.drawString(40, y, chunk)
            y -= 14
    if not rows:
        pdf.drawString(40, y, "Sin datos")
    pdf.save()
