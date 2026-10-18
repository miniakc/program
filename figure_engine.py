"""PDF figure regions: composite the original page only inside graphic bounds.
Text over a graphic stays in the composite. Ordinary body text is not an image.
Ambiguous full-page scans require explicit crop selection instead of exporting
an entire scanned page as a figure.
"""
import math

def area(b):return max(0,b[2]-b[0])*max(0,b[3]-b[1])
def union(a,b):return (min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3]))
def touches(a,b,gap=0):return a[0]<=b[2]+gap and b[0]<=a[2]+gap and a[1]<=b[3]+gap and b[1]<=a[3]+gap
def clip(b,w,h):return (max(0,b[0]),max(0,b[1]),min(w,b[2]),min(h,b[3]))
def group(boxes,gap=5):
    result=[]
    for b in boxes:
        changed=True
        while changed:
            changed=False;rest=[]
            for old in result:
                if touches(b,old,gap):b=union(b,old);changed=True
                else:rest.append(old)
            result=rest
        result.append(b)
    return result

def detect_regions(page):
    import pypdfium2 as pdfium
    w,h=page.get_size();graphics=[];texts=[];scan=False
    for obj in page.get_objects():
        if obj.type not in (pdfium.raw.FPDF_PAGEOBJ_IMAGE,pdfium.raw.FPDF_PAGEOBJ_PATH,pdfium.raw.FPDF_PAGEOBJ_TEXT,pdfium.raw.FPDF_PAGEOBJ_SHADING):continue
        b=clip(obj.get_bounds(),w,h)
        if not all(math.isfinite(v) for v in b) or area(b)<=0:continue
        if obj.type==pdfium.raw.FPDF_PAGEOBJ_TEXT:texts.append(b);continue
        ratio=area(b)/(w*h)
        if ratio>.65:
            if obj.type==pdfium.raw.FPDF_PAGEOBJ_IMAGE:scan=True
            continue # page backgrounds / full scans are never exported as figures
        bw,bh=b[2]-b[0],b[3]-b[1]
        # Ignore thin long rules, tiny decoration and text-sized specks.
        if max(bw,bh)<12 or (min(bw,bh)<1.5 and max(bw,bh)>w*.65):continue
        graphics.append(b)
    boxes=group(graphics)
    boxes=[b for b in boxes if b[2]-b[0]>=25 and b[3]-b[1]>=25 and area(b)>=1000]
    expanded=[]
    for b in boxes:
        original=b
        for text in texts:
            # Include full labels that overlap the actual graphic, without
            # recursively absorbing nearby paragraph text after expansion.
            if touches(original,text,1):b=union(b,text)
        expanded.append(clip((b[0]-3,b[1]-3,b[2]+3,b[3]+3),w,h))
    boxes=group(expanded,2)
    boxes=[b for b in boxes if area(b)<w*h*.85]
    return sorted(boxes,key=lambda b:(-b[3],b[0])),scan

def render_region(page,box,scale=2.5):
    w,h=page.get_size();box=clip(box,w,h)
    if area(box)<100:raise ValueError('그림 영역을 조금 더 크게 선택하세요.')
    if area(box)>w*h*.90:raise ValueError('페이지 전체 대신 그림 영역만 선택하세요.')
    scale=min(scale,(8_000_000/max(area(box),1))**.5)
    bitmap=page.render(scale=scale,crop=(box[0],box[1],w-box[2],h-box[3]))
    try:return bitmap.to_pil().convert('RGB').copy()
    finally:bitmap.close()
