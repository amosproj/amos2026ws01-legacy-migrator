# Build documentation sources

The Markdown files in this folder are the wiki-ready pages. `Index.md` is the navigation page. `render_pdf.py` formats those pages into the PDF at `../build-documentation.pdf` using ReportLab; no Pandoc is used.

Requirements: Python 3.12 and ReportLab 5.1.0 or a compatible ReportLab release.

From this folder, run:

~~~bash
python3 render_pdf.py
~~~
