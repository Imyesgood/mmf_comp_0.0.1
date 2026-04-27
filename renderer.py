"""
renderer.py  ·  표 HTML 생성 & PNG 이미지 저장
"""
import io
import base64

# ── 색상 팔레트 (원본 표 기준) ─────────────────────────
C_HEADER_BG   = "#4a7c59"   # 진한 녹색 헤더
C_HEADER_FG   = "#ffffff"
C_ROW_LABEL_BG = "#f5f5f5"  # 행 레이블 배경
C_EVEN_BG     = "#ffffff"
C_ODD_BG      = "#f0f7f0"   # 연한 초록 줄
C_HIGHLIGHT_BG = "#fffde7"  # 유입액 행 노란배경
C_HIGHLIGHT_FG = "#000000"
C_NEG          = "#d32f2f"   # 음수 빨간색
C_BORDER       = "#c8d8c8"


def _is_negative(val: str) -> bool:
    try:
        return float(val.replace(",", "")) < 0
    except Exception:
        return False


def _cell_style(label, val, is_highlight, col_idx) -> str:
    bg = C_HIGHLIGHT_BG if is_highlight else (C_ODD_BG if col_idx % 2 == 0 else C_EVEN_BG)
    fg = C_NEG if (is_highlight or label in _RED_LABELS) and _is_negative(val) else C_HIGHLIGHT_FG
    fw = "bold" if is_highlight else "normal"
    return f"background:{bg};color:{fg};font-weight:{fw};"


_RED_LABELS = set()  # render_html에서 주입


def render_html(full_table, fund_order, fund_display,
                highlight_rows, red_if_negative) -> str:
    global _RED_LABELS
    _RED_LABELS = red_if_negative

    cols = fund_order
    headers = [fund_display.get(c, c).replace("\n", "<br>") for c in cols]

    rows_html = ""
    for i, (label, row_data) in enumerate(full_table.items()):
        is_hl = label in highlight_rows
        label_bg = C_HIGHLIGHT_BG if is_hl else (C_ODD_BG if i % 2 == 1 else C_ROW_LABEL_BG)
        label_fw = "bold" if is_hl else "normal"
        label_display = label.replace("\n", "<br>")

        cells = f'<td style="background:{label_bg};font-weight:{label_fw};padding:6px 10px;border:1px solid {C_BORDER};white-space:nowrap;">{label_display}</td>'
        for j, code in enumerate(cols):
            val = row_data.get(code, "-")
            is_hl_cell = is_hl
            bg = C_HIGHLIGHT_BG if is_hl_cell else (C_ODD_BG if i % 2 == 1 else C_EVEN_BG)
            fg = C_NEG if label in red_if_negative and _is_negative(str(val)) else "#000000"
            fw = "bold" if is_hl_cell else "normal"
            val_display = str(val).replace("\n", "<br>")
            cells += (
                f'<td style="background:{bg};color:{fg};font-weight:{fw};'
                f'padding:6px 14px;border:1px solid {C_BORDER};text-align:center;">'
                f'{val_display}</td>'
            )
        rows_html += f"<tr>{cells}</tr>\n"

    header_cells = f'<th style="background:{C_HEADER_BG};color:{C_HEADER_FG};padding:8px 14px;border:1px solid {C_BORDER};">펀드명</th>'
    for h in headers:
        header_cells += (
            f'<th style="background:{C_HEADER_BG};color:{C_HEADER_FG};'
            f'padding:8px 14px;border:1px solid {C_BORDER};text-align:center;">{h}</th>'
        )

    html = f"""
<style>
  table.mmf {{ border-collapse:collapse; font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif; font-size:13px; width:100%; }}
  table.mmf th, table.mmf td {{ border:1px solid {C_BORDER}; }}
</style>
<table class="mmf">
  <thead><tr>{header_cells}</tr></thead>
  <tbody>{rows_html}</tbody>
</table>
"""
    return html


# ── PNG 이미지 생성 (imgkit → weasyprint → playwright 순으로 시도) ──
def render_image(full_table, fund_order, fund_display,
                 highlight_rows, red_if_negative) -> bytes:
    html = render_html(full_table, fund_order, fund_display,
                       highlight_rows, red_if_negative)

    full_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  body {{ margin:20px; font-family:'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',sans-serif; }}
  table.mmf {{ border-collapse:collapse; font-size:13px; }}
  table.mmf th, table.mmf td {{ border:1px solid {C_BORDER}; }}
</style>
</head><body>{html}</body></html>"""

    # 1) playwright (고화질)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            page.set_content(full_html, wait_until="networkidle")
            # 표 크기에 맞게
            table = page.query_selector("table.mmf")
            bbox  = table.bounding_box()
            img   = page.screenshot(
                clip={"x": bbox["x"]-10, "y": bbox["y"]-10,
                      "width": bbox["width"]+20, "height": bbox["height"]+20},
                full_page=False,
            )
            browser.close()
        return img
    except Exception:
        pass

    # 2) weasyprint
    try:
        import weasyprint
        pdf = weasyprint.HTML(string=full_html).write_pdf()
        # pdf → png via poppler
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf); pdf_path = f.name
        png_path = pdf_path.replace(".pdf", "")
        subprocess.run(["pdftoppm", "-r", "200", "-png", "-singlefile", pdf_path, png_path], check=True)
        with open(png_path + ".png", "rb") as f:
            data = f.read()
        os.unlink(pdf_path); os.unlink(png_path + ".png")
        return data
    except Exception:
        pass

    # 3) fallback: matplotlib
    return _render_matplotlib(full_table, fund_order, fund_display,
                               highlight_rows, red_if_negative)


def _render_matplotlib(full_table, fund_order, fund_display,
                        highlight_rows, red_if_negative):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import numpy as np

    # 한글 폰트
    font_candidates = [
        # Windows
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
        # Linux/Mac
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    font_set = False
    for fc in font_candidates:
        if os.path.exists(fc):
            fm.fontManager.addfont(fc)
            plt.rcParams["font.family"] = fm.FontProperties(fname=fc).get_name()
            font_set = True
            break

    if not font_set:
        # 시스템 폰트에서 한글 지원 폰트 자동 탐색
        kor_fonts = [
            f.name for f in fm.fontManager.ttflist
            if any(k in f.name.lower() for k in ["malgun", "nanum", "gothic", "noto", "cjk", "kr"])
        ]
        if kor_fonts:
            plt.rcParams["font.family"] = kor_fonts[0]

    labels = list(full_table.keys())
    cols   = fund_order
    n_rows = len(labels)
    n_cols = len(cols) + 1  # +1 for row label

    col_w  = 1.5
    row_h  = 0.45
    fig_w  = col_w * n_cols + 1
    fig_h  = row_h * (n_rows + 1) + 0.3

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    # 헤더
    header_labels = ["펀드명"] + [fund_display.get(c, c).replace("\n", "\n") for c in cols]
    for j, h in enumerate(header_labels):
        ax.add_patch(plt.Rectangle(
            (j * col_w, n_rows * row_h), col_w, row_h,
            color="#4a7c59", zorder=2
        ))
        ax.text(j * col_w + col_w / 2, n_rows * row_h + row_h / 2, h,
                ha="center", va="center", fontsize=7.5, color="white",
                fontweight="bold", zorder=3, wrap=True,
                multialignment="center")

    # 데이터 행
    for i, (label, row_data) in enumerate(full_table.items()):
        is_hl = label in highlight_rows
        row_y = (n_rows - 1 - i) * row_h

        # 행 레이블
        label_bg = "#fffde7" if is_hl else ("#f0f7f0" if i % 2 == 1 else "#f5f5f5")
        ax.add_patch(plt.Rectangle((0, row_y), col_w, row_h, color=label_bg, zorder=2))
        ax.text(col_w / 2, row_y + row_h / 2,
                label.replace("\n", "\n"),
                ha="center", va="center", fontsize=7, zorder=3,
                fontweight="bold" if is_hl else "normal",
                multialignment="center")

        # 값 셀
        for j, code in enumerate(cols):
            val = str(row_data.get(code, "-"))
            cell_bg = "#fffde7" if is_hl else ("#f0f7f0" if i % 2 == 1 else "#ffffff")
            neg = label in red_if_negative and _is_negative(val)
            fg  = "#d32f2f" if neg else "#000000"
            ax.add_patch(plt.Rectangle(
                ((j + 1) * col_w, row_y), col_w, row_h,
                color=cell_bg, zorder=2
            ))
            ax.text((j + 1) * col_w + col_w / 2, row_y + row_h / 2,
                    val.replace("\n", "\n"),
                    ha="center", va="center", fontsize=7.5, color=fg,
                    fontweight="bold" if is_hl else "normal", zorder=3)

    # 격자선
    for i in range(n_rows + 2):
        ax.axhline(i * row_h, color=C_BORDER, linewidth=0.5, zorder=1)
    for j in range(n_cols + 1):
        ax.axvline(j * col_w, color=C_BORDER, linewidth=0.5, zorder=1)

    ax.set_xlim(0, n_cols * col_w)
    ax.set_ylim(0, (n_rows + 1) * row_h)
    plt.tight_layout(pad=0.2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


import os  # 이미 상단에 없으니 보장

def render_excel(full_table, fund_order, fund_display,
                 highlight_rows, red_if_negative) -> bytes:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MMF 피어그룹 비교표"

    # ── 스타일 정의 ──────────────────────────────────────
    thin = Side(style="thin", color="C8D8C8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def make_fill(hex_color):
        return PatternFill("solid", fgColor=hex_color.lstrip("#"))

    header_fill   = make_fill(C_HEADER_BG)
    odd_fill      = make_fill("F0F7F0")
    even_fill     = make_fill("FFFFFF")
    label_odd     = make_fill("F0F7F0")
    label_even    = make_fill("F5F5F5")
    highlight_fill = make_fill("FFFDE7")
    neg_font_color = "D32F2F"

    # ── 헤더 행 ─────────────────────────────────────────
    ws.cell(1, 1, "펀드명").font = Font(bold=True, color="FFFFFF", name="맑은 고딕")
    ws.cell(1, 1).fill      = header_fill
    ws.cell(1, 1).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.cell(1, 1).border    = border
    ws.row_dimensions[1].height = 30

    for j, code in enumerate(fund_order, start=2):
        display = fund_display.get(code, code).replace("\n", "\n")
        cell = ws.cell(1, j, display)
        cell.font      = Font(bold=True, color="FFFFFF", name="맑은 고딕")
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = border

    # ── 데이터 행 ────────────────────────────────────────
    for i, (label, row_data) in enumerate(full_table.items(), start=2):
        is_hl = label in highlight_rows
        row_fill     = highlight_fill if is_hl else (odd_fill  if i % 2 == 0 else even_fill)
        label_fill   = highlight_fill if is_hl else (label_odd if i % 2 == 0 else label_even)

        # 행 레이블
        lc = ws.cell(i, 1, label)
        lc.font      = Font(bold=is_hl, name="맑은 고딕")
        lc.fill      = label_fill
        lc.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        lc.border    = border
        ws.row_dimensions[i].height = 28 if "\n" in label else 20

        # 값 셀
        for j, code in enumerate(fund_order, start=2):
            val = str(row_data.get(code, "-"))
            is_neg = label in red_if_negative and _is_negative(val)
            fc = ws.cell(i, j, val)
            fc.font      = Font(bold=is_hl, color=neg_font_color if is_neg else "000000", name="맑은 고딕")
            fc.fill      = row_fill
            fc.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            fc.border    = border

    # ── 열 너비 ─────────────────────────────────────────
    ws.column_dimensions["A"].width = 22
    for j in range(2, len(fund_order) + 2):
        ws.column_dimensions[get_column_letter(j)].width = 14

    # ── 바이트 반환 ──────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()