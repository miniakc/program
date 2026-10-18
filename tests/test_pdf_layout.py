import hashlib,json,tempfile,threading,unittest
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject,RectangleObject,ArrayObject,TextStringObject,NumberObject
from pipeline import extract_pdf
from exchange import AssetStore,markdown
from pdf_layout import paragraphs,reading_order

def textbook_fixture(path,trim=True,rotation=0):
    writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
    if trim:page[NameObject('/TrimBox')]=RectangleObject((30,30,570,770))
    if rotation:page.rotate(rotation)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'''
BT /F1 11 Tf 60 720 Td (Body before the callout. This sentence is a normal paragraph.) Tj ET
BT /F1 11 Tf 60 705 Td (The second visual line continues the paragraph.) Tj ET
.9 .96 .97 rg 60 440 480 140 re f
.3 .1 .35 rg 60 560 480 20 re f
1 1 1 rg BT /F1 10 Tf 70 566 Td (BOX 1-1 Important signs) Tj ET
0 0 0 rg
BT /F1 10 Tf 72 540 Td [(- Hot) -1100 (food) -1300 (or) -1200 (liquid) -1200 (in) -1200 (the) -1200 (mouth)] TJ ET
BT /F1 10 Tf 72 525 Td (- Unable to swallow saliva) Tj ET
BT /F1 10 Tf 72 510 Td (- Stridor) Tj ET
BT /F1 10 Tf 72 482 Td (These findings require assessment.) Tj ET
BT /F1 10 Tf 72 468 Td (Do not infer a diagnosis from one sign alone.) Tj ET
BT /F1 11 Tf 60 415 Td (Body after the box. Keep this text after the callout.) Tj ET
0 0 0 RG .6 w 60 250 480 100 re S
60 300 m 540 300 l S 220 250 m 220 350 l S 380 250 m 380 350 l S
BT /F1 10 Tf 70 325 Td (Item) Tj 160 0 Td (Meaning) Tj 160 0 Td (Action) Tj ET
BT /F1 10 Tf 70 275 Td (A) Tj 160 0 Td (Check) Tj 160 0 Td (Record) Tj ET
0 .6 .3 RG 3 w 340 80 120 90 re S 340 80 m 460 170 l S
0 0 0 rg BT /F1 10 Tf 350 115 Td (DIAGRAM LABEL) Tj ET
0 0 0 RG .7 w 285 12 m 315 12 l S 300 0 m 300 26 l S
0 0 25 25 re S 575 775 25 25 re S
0 375 30 50 re S 0 400 m 30 400 l S 15 375 m 15 425 l S
BT /F1 7 Tf 40 12 Td (production_job.indd 2026-10-18) Tj ET
''');page[NameObject('/Contents')]=writer._add_object(stream);writer.write(path)

class LayoutTests(unittest.TestCase):
    def test_box_spacing_lists_table_and_body_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pdf=root/'textbook.pdf';textbook_fixture(pdf)
            pages=extract_pdf(pdf,root/'cache',threading.Event(),lambda _:None);p=pages[0]
            self.assertEqual(p['layout_version'],3);self.assertEqual(p['method'],'text')
            md=p['markdown'];self.assertIn('> **BOX 1-1 Important signs**',md)
            self.assertIn('> - Hot food or liquid in the mouth',md);self.assertIn('> - Unable to swallow saliva',md)
            self.assertNotIn('  ',md);self.assertNotIn('production_job',md)
            self.assertLess(md.index('Body before'),md.index('BOX 1-1'));self.assertLess(md.index('BOX 1-1'),md.index('Body after'))
            self.assertIn('| Item | Meaning | Action |',md);self.assertIn('| A | Check | Record |',md)
            self.assertEqual([b['kind'] for b in p['blocks']].count('callout'),1)
            self.assertEqual([b['kind'] for b in p['blocks']].count('table'),1)
            assets=AssetStore(root/'assets');digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
            entries=assets.extract(pdf,digest,threading.Event(),lambda _:None,pages=pages)
            self.assertEqual(len(entries),1);self.assertLess(entries[0]['box'][3],200)
            out=markdown({'name':'Textbook','digest':digest,'pages':pages},entries)
            self.assertEqual(out.count('!['),1);self.assertLess(out.index('| A |'),out.index('![그림'))
            # Old pypdf-only cache cannot be reused by the new layout engine.
            old=root/'cache'/(digest+'-auto');old.mkdir();(old/'1.json').write_text('{"page":1,"text":"BROKEN CACHE"}')
            again=extract_pdf(pdf,root/'cache',threading.Event(),lambda _:None)
            self.assertEqual(again,pages)
    def test_margin_marks_without_trim_and_legacy_images_retained(self):
        import pypdfium2 as pdfium
        from figure_engine import detect_regions
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pdf=root/'marks.pdf';textbook_fixture(pdf,trim=False)
            document=pdfium.PdfDocument(pdf);page=document[0]
            try:
                boxes,_=detect_regions(page)
                self.assertTrue(boxes);self.assertTrue(all(b[0]>30 and b[1]>30 and b[2]<570 and b[3]<770 for b in boxes))
            finally:page.close();document.close()
            digest=hashlib.sha256(pdf.read_bytes()).hexdigest();assets=AssetStore(root/'assets')
            legacy=assets.root/(digest[:16]+'_p0001_figure001.png');legacy.write_bytes(b'old image bytes')
            (assets.root/(digest+'.figures-v2.json')).write_text(json.dumps({'images':[{'id':legacy.name}]}))
            entries=assets.extract(pdf,digest,threading.Event(),lambda _:None)
            self.assertEqual(legacy.read_bytes(),b'old image bytes');self.assertTrue(all(e['id']!=legacy.name for e in entries))
    def test_two_columns_do_not_interleave(self):
        def line(x,y,text):return {'box':[x,y,x+100,y+10],'kind':'line','text':text,'size':10}
        lines=[line(20,10,'left one'),line(20,25,'left two'),line(240,10,'right one'),line(240,25,'right two')]
        self.assertEqual([i['text'] for i in reading_order(lines)],['left one','left two','right one','right two'])
    def test_korean_paragraphs_and_bullets(self):
        def line(y,text,x=10):return {'box':[x,y,x+300,y+10],'text':text,'size':10}
        result=paragraphs([line(10,'상부 기도 폐쇄를 시사하는 네 가지 중요 징후'),line(40,'• 뜨거운 음식을 입 안에 넣고 말할 때 나타나는 목소리'),line(54,'• 침을 삼키지 못함'),line(84,'처음 두 징후만으로 단정할 수 없다.'),line(98,'호흡곤란도 주목해야 할 증상이다.')])
        self.assertIn('- 뜨거운 음식을',result);self.assertIn('\n- 침을',result);self.assertIn('\n\n처음',result)
    def test_rotated_figures_match_display_coordinates(self):
        import pypdfium2 as pdfium
        from figure_engine import detect_regions,render_region
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'rotated.pdf';textbook_fixture(path,rotation=90)
            doc=pdfium.PdfDocument(path);page=doc[0]
            try:
                boxes,_=detect_regions(page);self.assertTrue(boxes)
                self.assertTrue(any(b[0]<200 and b[1]<300 for b in boxes))
                for b in boxes:self.assertGreater(render_region(page,b).width,10)
            finally:page.close();doc.close()
    def test_offset_cropbox_keeps_text_and_figure_coordinates_aligned(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'crop.pdf';textbook_fixture(path)
            writer=PdfWriter();page=writer.add_page(PdfReader(path).pages[0]);page.cropbox=RectangleObject((30,30,570,770));writer.write(path)
            pages=extract_pdf(path,root/'cache',threading.Event(),lambda _:None)
            self.assertEqual(pages[0]['layout_size'],[540,740])
            assets=AssetStore(root/'assets');digest=hashlib.sha256(path.read_bytes()).hexdigest();entries=assets.extract(path,digest,threading.Event(),lambda _:None,pages=pages)
            self.assertEqual(len(entries),1);self.assertLess(entries[0]['box'][3],170)
    def test_merged_table_retains_rowspan_and_empty_cells(self):
        import pdfplumber
        from pdf_layout import analyze
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'merged.pdf';writer=PdfWriter();page=writer.add_blank_page(400,400)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject();stream.set_data(b'40 160 320 160 re S 200 160 m 200 320 l S 200 240 m 360 240 l S BT /F1 12 Tf 50 280 Td (Merged) Tj ET BT /F1 12 Tf 210 280 Td (Top) Tj ET')
            page[NameObject('/Contents')]=writer._add_object(stream);writer.write(path)
            with pdfplumber.open(path) as doc:result=analyze(doc.pages[0])
            self.assertIn('rowspan="2"',result['markdown']);self.assertIn('<td></td>',result['markdown']);self.assertIn('Merged',result['text'])
    def test_korean_native_unicode_and_word_spaces(self):
        import pdfplumber
        from pdf_layout import analyze
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'korean.pdf';writer=PdfWriter();page=writer.add_blank_page(500,500)
            text='상부 기도 폐쇄를 시사하는 네 가지 중요 징후';mapping=DecodedStreamObject()
            chars=set(text);pairs='\n'.join(f'<{ord(c):04x}> <{ord(c):04x}>' for c in chars)
            mapping.set_data(('/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Test def /CMapType 2 def 1 begincodespacerange <0000> <ffff> endcodespacerange '+str(len(chars))+' beginbfchar\n'+pairs+'\nendbfchar endcmap CMapName currentdict /CMap defineresource pop end end').encode())
            info=DictionaryObject({NameObject('/Registry'):TextStringObject('Adobe'),NameObject('/Ordering'):TextStringObject('Identity'),NameObject('/Supplement'):NumberObject(0)})
            cid=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/CIDFontType2'),NameObject('/BaseFont'):NameObject('/Test'),NameObject('/CIDSystemInfo'):info,NameObject('/DW'):NumberObject(1000)})
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type0'),NameObject('/BaseFont'):NameObject('/Test'),NameObject('/Encoding'):NameObject('/Identity-H'),NameObject('/DescendantFonts'):ArrayObject([writer._add_object(cid)]),NameObject('/ToUnicode'):writer._add_object(mapping)})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            stream=DecodedStreamObject();stream.set_data(('BT /F1 10 Tf 50 400 Td <'+text.encode('utf-16-be').hex()+'> Tj ET').encode());page[NameObject('/Contents')]=writer._add_object(stream);writer.write(path)
            with pdfplumber.open(path) as pdf:result=analyze(pdf.pages[0])
            self.assertEqual(result['text'],text)
