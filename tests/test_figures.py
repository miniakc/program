import hashlib, tempfile,threading,unittest
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import NameObject,DictionaryObject,NumberObject,DecodedStreamObject,ArrayObject
from PIL import Image
from exchange import AssetStore

def fixture(path):
    # Two figures on one page: embedded red raster + overlaid blue label,
    # and a separate vector diagram. Ordinary black body text above both.
    writer=PdfWriter();page=writer.add_blank_page(width=500,height=600)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    raster=DecodedStreamObject();raster.set_data(Image.new('RGB',(100,80),(220,50,30)).tobytes())
    raster.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),NameObject('/Width'):NumberObject(100),NameObject('/Height'):NumberObject(80),NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)}),NameObject('/XObject'):DictionaryObject({NameObject('/Im1'):writer._add_object(raster)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 14 Tf 40 550 Td (ORDINARY BODY TEXT) Tj ET\nq 160 0 0 130 40 300 cm /Im1 Do Q\n0 0 1 rg BT /F1 18 Tf 70 360 Td (OVERLAY LABEL) Tj ET\n0 .6 .3 RG 3 w 300 300 120 100 re S\n300 300 m 420 400 l S\nBT /F1 12 Tf 320 340 Td (VECTOR) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    # A full-page scan must never be silently exported as a whole-page PNG.
    page=writer.add_blank_page(width=500,height=600);page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im1'):writer._add_object(raster)})})
    stream=DecodedStreamObject();stream.set_data(b'q 500 0 0 600 0 0 cm /Im1 Do Q');page[NameObject('/Contents')]=writer._add_object(stream)
    writer.write(path)

class FigureTests(unittest.TestCase):
    def test_composite_labels_vector_and_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pdf=root/'fixture.pdf';fixture(pdf);assets=AssetStore(root/'assets');digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
            entries=assets.extract(pdf,digest,threading.Event(),lambda _:None)
            self.assertEqual(len(entries),2);self.assertEqual(assets.review_pages(digest),[2]);self.assertTrue(all(e['page']==1 for e in entries))
            self.assertTrue(all(e['box'][3]<500 for e in entries)) # excludes ordinary paragraph
            with Image.open(assets.resolve(entries[0]['id'])) as im:
                colors=list(im.convert('RGB').getdata());blue=sum(b>120 and r<100 for r,g,b in colors);red=sum(r>150 and b<100 for r,g,b in colors)
                self.assertGreater(blue,20);self.assertGreater(red,500) # overlay survived compositing
                self.assertLess(im.width,700);self.assertLess(im.height,500)
            assets.set_regions(digest,2,[(40,100,240,300)]);updated=assets.extract(pdf,digest,threading.Event(),lambda _:None)
            self.assertEqual(len(updated),3);self.assertEqual(assets.review_pages(digest),[])
            self.assertFalse(any('_page.png' in e['id'] for e in updated))
    def test_old_cache_not_reused_as_figures(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pdf=root/'fixture.pdf';fixture(pdf);assets=AssetStore(root/'assets');digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
            (assets.root/(digest+'.json')).write_text('[{"id":"old_page.png","kind":"page","page":1}]')
            entries=assets.extract(pdf,digest,threading.Event(),lambda _:None)
            self.assertTrue(entries);self.assertTrue(all(e['kind']=='figure' for e in entries))
