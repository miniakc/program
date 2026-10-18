# Third-party notices

This development source uses Python (PSF license), Tcl/Tk, pypdf (BSD-3-Clause),
and PyInstaller (GPL with its distribution exception). An installer compiled
from this source must include the license texts belonging to the exact bundled
versions. build-windows.ps1 copies installed Python package license metadata;
the packager must also retain the Python and Tcl/Tk runtime license texts.

Marker, Surya, OCR models and problem-generation AI models are NOT included.
No permission to redistribute those models is asserted by this package.

Official references:
- https://docs.python.org/3/license.html
- https://www.tcl.tk/software/tcltk/license.html
- https://github.com/py-pdf/pypdf/blob/main/LICENSE
- https://pyinstaller.org/en/stable/license.html

## OCR distribution in version 0.2

Version 0.2 includes Tesseract, its Windows distribution dependencies and the
kor/eng tessdata_fast models. The OCR distribution's bundled license documents
are copied with its files. Tesseract and tessdata_fast are Apache-2.0; the
Windows dependency libraries have their own licenses, retained in the bundled
OCR distribution. pypdfium2 and its PDFium binary license documents are copied
from the installed packages. Pillow license metadata is included as well.

- https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE
- https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE
- https://github.com/pypdfium2-team/pypdfium2/blob/main/LICENSE
- https://github.com/python-pillow/Pillow/blob/main/LICENSE

The earlier note that OCR is not included applies only to version 0.1;
Marker and Surya remain absent in version 0.2.
