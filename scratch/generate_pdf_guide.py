"""
Convert README.md into a complete, beautifully formatted PDF document.
Uses official python-markdown parser with tables, fenced_code, and sane_lists extensions
to guarantee 100% of all content, steps, commands, and formatting are included.
"""

import sys
import os
import shutil
from pathlib import Path

try:
    import markdown
except ImportError:
    print("[ERROR] python-markdown not installed yet.")
    sys.exit(1)


def generate_pdf():
    project_root = Path(__file__).resolve().parent.parent
    readme_path = project_root / "README.md"
    pdf_path = project_root / "README.pdf"
    guide_pdf_path = project_root / "AutoScan_Pro_User_Guide.pdf"
    artifact_pdf_path = Path(r"C:\Users\Huzaifa Abbasi\.gemini\antigravity-ide\brain\55d0cba6-766a-4dee-bcaa-db230ad91671\AutoScan_Pro_User_Guide.pdf")

    if not readme_path.exists():
        print(f"[ERROR] {readme_path} not found.")
        sys.exit(1)

    md_content = readme_path.read_text(encoding="utf-8")

    # Use python-markdown to convert MD to clean HTML with all extensions enabled
    md_parser = markdown.Markdown(
        extensions=[
            'tables',
            'fenced_code',
            'sane_lists',
            'toc',
            'nl2br',
        ]
    )
    body_html = md_parser.convert(md_content)

    styled_document = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>AutoScan Pro - Complete User Guide & Manual</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 18mm 14mm 18mm 14mm;
    @bottom-right {{
      content: "Page " counter(page) " of " counter(pages);
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 8pt;
      color: #64748b;
    }}
    @bottom-left {{
      content: "AutoScan Pro — Complete User Guide & Manual";
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 8pt;
      color: #64748b;
    }}
  }}

  body {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #1e293b;
    background-color: #ffffff;
    margin: 0;
    padding: 0;
  }}

  /* Top Banner / Cover Header */
  h1 {{
    background-color: #0f172a;
    color: #00e5ff;
    padding: 20px 24px;
    margin-top: 0;
    margin-bottom: 20px;
    font-size: 22pt;
    font-weight: 700;
    border-radius: 6px;
    border-left: 6px solid #00e5ff;
  }}

  h2 {{
    color: #0f172a;
    font-size: 14pt;
    font-weight: 700;
    margin-top: 22px;
    margin-bottom: 10px;
    padding-bottom: 5px;
    border-bottom: 2px solid #cbd5e1;
    page-break-after: avoid;
  }}

  h3 {{
    color: #1e293b;
    font-size: 11.5pt;
    font-weight: 600;
    margin-top: 16px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }}

  p {{
    margin-top: 0;
    margin-bottom: 8px;
    color: #334155;
  }}

  hr {{
    border: 0;
    height: 1px;
    background: #cbd5e1;
    margin: 18px 0;
  }}

  /* Links */
  a {{
    color: #0284c7;
    text-decoration: none;
    font-weight: 600;
  }}

  /* Styled Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0;
    font-size: 9pt;
    page-break-inside: avoid;
  }}

  th {{
    background-color: #0f172a;
    color: #ffffff;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid #1e293b;
  }}

  td {{
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    color: #334155;
  }}

  tr:nth-child(even) td {{
    background-color: #f8fafc;
  }}

  /* Code Blocks */
  pre {{
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    margin: 10px 0;
    padding: 10px 12px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 8.8pt;
    color: #f1f5f9;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.4;
    page-break-inside: avoid;
  }}

  code {{
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 8.8pt;
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #cbd5e1;
  }}

  pre code {{
    background-color: transparent;
    color: inherit;
    padding: 0;
    border: none;
  }}

  /* Lists */
  ul, ol {{
    margin-top: 4px;
    margin-bottom: 10px;
    padding-left: 20px;
    color: #334155;
  }}

  li {{
    margin-bottom: 4px;
  }}

  /* Blockquotes / Alerts */
  blockquote {{
    background-color: #f0f9ff;
    border-left: 4px solid #0284c7;
    margin: 12px 0;
    padding: 8px 14px;
    color: #075985;
    font-size: 9.5pt;
    border-radius: 0 4px 4px 0;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""

    pdf_created = False

    # 1. Try WeasyPrint
    try:
        from weasyprint import HTML
        HTML(string=styled_document).write_pdf(str(pdf_path))
        pdf_created = True
        print(f"[SUCCESS] PDF generated via WeasyPrint at: {pdf_path}")
    except Exception as e:
        print(f"[INFO] WeasyPrint rendering attempt: {e}")

    # 2. Try xhtml2pdf if WeasyPrint wasn't available
    if not pdf_created:
        try:
            from xhtml2pdf import pisa
            with open(pdf_path, "wb") as f_pdf:
                pisa_status = pisa.CreatePDF(styled_document, dest=f_pdf, encoding="utf-8")
            if not pisa_status.err:
                pdf_created = True
                print(f"[SUCCESS] PDF generated via xhtml2pdf at: {pdf_path}")
        except Exception as e:
            print(f"[INFO] xhtml2pdf rendering attempt: {e}")

    if pdf_created and pdf_path.exists():
        shutil.copy2(pdf_path, guide_pdf_path)
        if artifact_pdf_path.parent.exists():
            shutil.copy2(pdf_path, artifact_pdf_path)
        print(f"[SUCCESS] Complete User Guide PDF saved to: {guide_pdf_path}")
        print(f"[SUCCESS] File size: {pdf_path.stat().st_size} bytes")

if __name__ == "__main__":
    generate_pdf()
