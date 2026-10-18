import json, tempfile, threading, unittest, zipfile
from pathlib import Path
from PIL import Image
from core import Store,parse_questions,parse_md
from exchange import AssetStore,QuizCountdown,export_bundle,markdown,export_xlsx,answer_text

def q(**kw):return dict(stem='그림에서 확인할 것은?',concept='그림 판단',explanation='그림의 근거',**kw)

class ExchangeTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.assets=AssetStore(self.root/'assets')
    def tearDown(self):self.tmp.cleanup()
    def test_mixed_schema_legacy_and_atomic(self):
        qs=parse_questions(json.dumps({'questions':[q(type='객관식',options=['가','나','다','라'],correct=0),q(type='OX',answer='x'),q(type='단답형',answer='명칭'),q(type='OX',showStem='예전 지문',showAnswer='O',options=['가','나','다','라'],correct=3)]},ensure_ascii=False))
        self.assertEqual(qs[1]['correct'],1);self.assertEqual(qs[3]['stem'],'예전 지문');self.assertEqual(answer_text(qs[3]),'O')
        db=Store(self.root/'bank.db')
        try:
            qs[1]['stem']='OX 지문';qs[2]['stem']='단답 지문';self.assertEqual(db.import_questions(qs),4)
            self.assertTrue(all(not x['approved'] for x in db.questions()))
        finally:db.db.close()
        for value in ['../a.png','https://example.com/a.png','images/a.png','한글.png']:
            with self.assertRaises(ValueError):parse_questions(json.dumps([q(type='OX',answer='O',images=[value])]))
        with self.assertRaises(ValueError):parse_questions(json.dumps([q(type='OX',answer='yes')]))
    def test_pdf_images_bundle_json_only_and_other_pc(self):
        im=Image.new('RGB',(500,300),'#e05030');pdf=self.root/'book.pdf';im.save(pdf,'PDF',resolution=72)
        import hashlib
        digest=hashlib.sha256(pdf.read_bytes()).hexdigest();events=[]
        entries=self.assets.extract(pdf,digest,threading.Event(),events.append)
        self.assertTrue(any(e['kind']=='page' for e in entries));self.assertTrue(any(e['kind']=='image' for e in entries))
        self.assertEqual(events[-1]['current'],1)
        doc={'name':'테스트.pdf','digest':digest,'pages':[{'page':1,'text':'원문 본문'}]};bundle=self.root/'material.zip';export_bundle(bundle,doc,self.assets,entries)
        with zipfile.ZipFile(bundle) as z:
            md=z.read('교재.md').decode();self.assertIn('개별 이미지',md);self.assertEqual(parse_md(md)[0]['page'],1);self.assertIn(entries[0]['id'],md)
        qq=parse_questions(json.dumps([q(type='OX',answer='O',images=[entries[0]['id']])]))[0]
        self.assertIsNotNone(self.assets.resolve(qq['images'][0]))
        other=AssetStore(self.root/'other');self.assertIsNone(other.resolve(qq['images'][0]));self.assertEqual(other.import_zip(bundle),len(entries));self.assertIsNotNone(other.resolve(qq['images'][0]))
        # Cache survives repeated export without re-rendering.
        self.assertEqual(self.assets.extract(pdf,digest,threading.Event(),lambda _:self.fail('unexpected re-render')),entries)
    def test_zip_path_and_collision(self):
        bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:z.writestr('images/../../escape.png',b'bad')
        with self.assertRaises(ValueError):self.assets.import_zip(bad)
        self.assertIsNone(self.assets.resolve('../escape.png'))
    def test_excel_native_text_and_bounds(self):
        qq=parse_questions(json.dumps([q(type='단답형',answer='=1+2',images=['test.png'],page=5,source='교재')]))[0]
        path=self.root/'questions.xlsx';export_xlsx(path,[qq])
        from xml.etree import ElementTree as E
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(path) as z:
            sheet=E.fromstring(z.read('xl/worksheets/sheet1.xml'));self.assertEqual(sheet.findall('.//s:f',ns),[])
            self.assertEqual(sheet.find('.//s:c[@r="J2"]//s:t',ns).text,'=1+2');self.assertEqual(sheet.find('.//s:c[@r="M2"]/s:v',ns).text,'5')
            self.assertIsNotNone(sheet.find('.//s:pane',ns));self.assertIsNotNone(sheet.find('s:autoFilter',ns))
        before=path.read_bytes();qq['stem']='x'*32768
        with self.assertRaises(ValueError):export_xlsx(path,[qq])
        self.assertEqual(path.read_bytes(),before)
    def test_countdown_wall_clock_and_reset(self):
        current=[100.0];timer=QuizCountdown(lambda:current[0]);self.assertIsNone(timer.remaining)
        timer.start();self.assertEqual(timer.remaining,10);current[0]+=3.2;self.assertEqual(timer.remaining,7)
        current[0]+=100;self.assertEqual(timer.remaining,0);timer.start();self.assertEqual(timer.remaining,10);timer.stop();self.assertIsNone(timer.remaining)
