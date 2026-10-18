"""Coordinate-based PDF text, callouts and ruled tables. No language model.

Coordinates in saved blocks are top-left, relative to the visible CropBox.
Keep plain source text separate from Markdown syntax for citation checks.
"""
import html,re,statistics

VERSION=4
BULLET=re.compile(r'^(?:[•·●▪‣◦\uf0b7]|[-–] )\s*')

def clean(text):return re.sub(r'[ \t\u00a0]+',' ',text or '').strip()
def box(obj):return (obj['x0'],obj['top'],obj['x1'],obj['bottom'])
def inside(inner,outer,tolerance=1):
    return inner[0]>=outer[0]-tolerance and inner[1]>=outer[1]-tolerance and inner[2]<=outer[2]+tolerance and inner[3]<=outer[3]+tolerance
def intersects(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
def intersect(a,b):return (max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3]))

def text_lines(page,split_columns=True):
    # layout=False never pads words to a fixed-width page grid. Use actual
    # PDF character positions, including TJ word gaps, to recover word spaces.
    words=page.extract_words(x_tolerance=1.8,x_tolerance_ratio=.18,y_tolerance=2.5,keep_blank_chars=False,return_chars=True)
    rows=[]
    for word in words:
        chars=word['chars'];word['_size']=statistics.median([c.get('size',10) for c in chars] or [10])
        baselines=[-c['matrix'][5] for c in chars if c.get('upright') and c.get('matrix')]
        word['_baseline']=statistics.median(baselines) if baselines else word['bottom']
    # Baselines are stable across Korean/Latin fonts whose ink bounds differ.
    # Small reference numbers are attached after the regular text rows exist.
    typical=statistics.median([w['_size'] for w in words] or [10]);small=[]
    for word in sorted(words,key=lambda w:(w['_baseline'],w['x0'])):
        if word['_size']<typical*.76 and len(word['text'])<=4:small.append(word);continue
        row=next((r for r in reversed(rows[-8:]) if abs(r['baseline']-word['_baseline'])<=max(1.5,min(r['size'],word['_size'])*.2)),None)
        if row is None:row={'baseline':word['_baseline'],'size':word['_size'],'words':[]};rows.append(row)
        row['words'].append(word)
    for word in small:
        candidates=[r for r in rows if abs(r['baseline']-word['_baseline'])<r['size']*.85]
        row=min(candidates,key=lambda r:abs(r['baseline']-word['_baseline'])) if candidates else None
        if row is None:rows.append({'baseline':word['_baseline'],'size':word['_size'],'words':[word]})
        else:word['_reference']=True;row['words'].append(word)
    # A single wide justified space is not a column. Require a recurring gutter.
    row_words=[sorted(r['words'],key=lambda w:w['x0']) for r in rows]
    gaps=[[(a['x1'],b['x0']) for a,b in zip(ws,ws[1:]) if b['x0']-a['x1']>max(18,r['size']*2.2)] for r,ws in zip(rows,row_words)]
    def gutter(x):
        eligible=[i for i,ws in enumerate(row_words) if ws and ws[0]['x0']<x<ws[-1]['x1']]
        return sum(any(a<x<b for a,b in gaps[i]) for i in eligible)>=max(2,len(eligible)*.4)
    lines=[]
    for row in rows:
        current=[]
        for word in sorted(row['words'],key=lambda w:w['x0']):
            if split_columns and current and word['x0']-current[-1]['x1']>max(18,row['size']*2.2) and gutter((word['x0']+current[-1]['x1'])/2):
                lines.append(make_line(current));current=[]
            current.append(word)
        if current:lines.append(make_line(current))
    return sorted(lines,key=lambda x:(x['box'][1],x['box'][0]))

def make_line(words):
    text=''
    for i,w in enumerate(words):text+=('' if not i or w.get('_reference') and w['x0']-words[i-1]['x1']<w['_size'] else ' ')+w['text']
    return {'kind':'line','box':[min(w['x0'] for w in words),min(w['top'] for w in words),max(w['x1'] for w in words),max(w['bottom'] for w in words)],'text':clean(text),
            'baseline':statistics.median([w['_baseline'] for w in words if not w.get('_reference')] or [0]),'size':statistics.median([w['_size'] for w in words if not w.get('_reference')] or [10])}

def reading_order(items):
    """Recursive whitespace cuts; read each column before the next column."""
    if len(items)<2:return items
    for axis,minimum in ((0,18),(1,2)):
        intervals=sorted((i['box'][axis],i['box'][axis+2]) for i in items);end=intervals[0][1];gaps=[]
        for start,stop in intervals[1:]:
            if start-end>=minimum:gaps.append((start-end,(start+end)/2))
            end=max(end,stop)
        if gaps:
            _,cut=max(gaps);left=[i for i in items if i['box'][axis+2]<=cut];right=[i for i in items if i['box'][axis]>=cut]
            if left and right and len(left)+len(right)==len(items):return reading_order(left)+reading_order(right)
    return sorted(items,key=lambda i:(round(i['box'][1]/3),i['box'][0]))

def sentence_lines(text):
    """Split at conservative sentence boundaries, retaining source wording.

    Markdown hard breaks keep sentence lines visible in both a text editor
    and a rendered Markdown reader. Decimal points and abbreviations stay.
    """
    text=clean(text);parts=[];start=0;depth=0
    abbreviations={'e.g.','i.e.','etc.','vs.','dr.','mr.','mrs.','ms.','prof.','fig.','no.','al.','vol.','pp.'}
    closing='\"\u201d\u2019\')]}\u300d\u300f'
    for i,char in enumerate(text):
        if char in '([{':depth+=1
        elif char in ')]}':depth=max(0,depth-1)
        if char not in '.!?。' or depth:continue
        if char=='.':
            if i and i+1<len(text) and text[i-1].isdigit() and text[i+1].isdigit():continue
            if i+1<len(text) and text[i+1] in '.!?':continue
            token=text[:i+1].split()[-1].lower().lstrip('([{\"\u201c\u2018')
            if token in abbreviations or re.fullmatch(r'(?:[a-z]\.)+',token) or token.endswith('...'):continue
            if re.fullmatch(r'\d+\.',text[start:i+1].strip()):continue
        end=i+1
        while end<len(text) and text[end] in closing:end+=1
        reference=re.match(r'(?:\d{1,3}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)(?=\s|$)',text[end:])
        if reference:end+=len(reference[0])
        if end<len(text) and not text[end].isspace():continue
        if end<len(text):parts.append(text[start:end].strip());start=end
    if text[start:].strip():parts.append(text[start:].strip())
    return '  \n'.join(parts)

def paragraphs(lines):
    if not lines:return ''
    def baseline(line):return line.get('baseline',line['box'][3])
    sizes=[l['size'] for l in lines];size=statistics.median(sizes)
    steps=[baseline(b)-baseline(a) for a,b in zip(lines,lines[1:]) if size*.7<=baseline(b)-baseline(a)<=size*2.2]
    leading=statistics.median(steps) if steps else size*1.4
    left=min(l['box'][0] for l in lines);width=max(l['box'][2] for l in lines)-left
    separator=' '
    result=[];last=None;last_bullet=False
    for line in lines:
        text=clean(line['text']);bullet=bool(BULLET.match(text))
        if bullet:text='- '+BULLET.sub('',text)
        if last is None:result.append(text)
        else:
            step=baseline(line)-baseline(last)
            numbered=bool(re.match(r'^(?:\d+[.)]|[①-⑳])\s',text))
            # Paragraphs depend on baseline leading / indentation, not glyph
            # ink height. Latin runs, superscripts and tight CJK boxes used to
            # make ordinary wrapped lines look like separate paragraphs.
            finished=bool(re.search(r'[.!?。][”’"\')\]]*$',last['text']))
            indent=line['box'][0]-left
            new=(bullet or numbered or step>leading*1.5 or line['size']>last['size']*1.2 or line['size']<last['size']*.8 or step<0 or (finished and indent>size*.7) or (last_bullet and indent<size*.5 and step>leading*1.15))
            if new:result.append(text)
            else:result[-1]+=separator+text
        last=line;last_bullet=bullet
    out=[]
    for index,value in enumerate(result):
        # List items and table cells retain their own structure; body prose
        # is reflowed first and then broken only at sentence boundaries.
        if not value.startswith('- ') and not re.match(r'^\d+[.)]\s',value):value=sentence_lines(value)
        if index and value.startswith('- ') and result[index-1].startswith('- '):out.append('\n'+value)
        else:out.append(('\n\n' if out else '')+value)
    return ''.join(out)

def ocr_formats(text):
    flow=[]
    for part in re.split(r'\n\s*\n',text.strip()):
        raw=[clean(line) for line in part.splitlines() if clean(line)]
        lines=[{'text':line,'size':10,'box':[0,i*14,400,i*14+10]} for i,line in enumerate(raw)]
        if lines:flow.append(paragraphs(lines))
    return '\n\n'.join(flow)

def table_text(page,table):
    xs=sorted({round(c[i],2) for c in table.cells for i in (0,2)});ys=sorted({round(c[i],2) for c in table.cells for i in (1,3)})
    if len(xs)<3 or len(ys)<3:return None
    cells=[];plain=[];merged=False
    for c in table.cells:
        sub=page.crop(c,strict=False);value=paragraphs(text_lines(sub,split_columns=False));plain.append(value)
        x=xs.index(round(c[0],2));y=ys.index(round(c[1],2));colspan=xs.index(round(c[2],2))-x;rowspan=ys.index(round(c[3],2))-y
        merged|=colspan>1 or rowspan>1;cells.append((y,x,rowspan,colspan,value))
    if not any(clean(v) for v in plain):return None
    if merged:
        rows=[]
        for y in range(len(ys)-1):
            cells_in_row=[]
            for yy,x,rs,cs,value in sorted(cells):
                if yy!=y:continue
                attrs=(f' rowspan="{rs}"' if rs>1 else '')+(f' colspan="{cs}"' if cs>1 else '')
                cells_in_row.append('<td'+attrs+'>'+html.escape(value).replace('\n','<br>')+'</td>')
            rows.append('<tr>'+''.join(cells_in_row)+'</tr>')
        md='<table>\n'+'\n'.join(rows)+'\n</table>'
    else:
        rows=[['']*(len(xs)-1) for _ in range(len(ys)-1)]
        for y,x,rs,cs,value in cells:rows[y][x]=value.replace('\\','\\\\').replace('|','\\|').replace('\n','<br>')
        def row(values):return '| '+' | '.join(values)+' |'
        md=row(rows[0])+'\n'+row(['---']*len(rows[0]))+'\n'+'\n'.join(row(r) for r in rows[1:])
    return {'kind':'table','box':list(table.bbox),'text':'\n'.join(plain),'markdown':md}

def analyze(page):
    visible=intersect(page.mediabox,page.cropbox);paper=intersect(visible,getattr(page,'trimbox',visible))
    if paper[2]<=paper[0] or paper[3]<=paper[1]:paper=visible
    content=page.crop(paper,strict=False).dedupe_chars(tolerance=.5)
    lines=text_lines(content);special=[]
    # Only ruled grids with at least two rows and columns qualify as tables.
    # A single surrounding rectangle remains a callout, not a fake table.
    for table in content.find_tables({'vertical_strategy':'lines','horizontal_strategy':'lines','snap_tolerance':2,'join_tolerance':2}):
        result=table_text(content,table)
        if result:special.append(result)
    candidates=[]
    for rect in content.rects:
        b=box(rect);w=b[2]-b[0];h=b[3]-b[1]
        if w<80 or h<28 or w*h>page.width*page.height*.7:continue
        if any(intersects(b,s['box']) for s in special):continue
        enclosed=[line for line in lines if inside(line['box'],b,2)]
        if len(enclosed)<2 or sum(len(l['text']) for l in enclosed)<30:continue
        # Publishers sometimes rasterize just the coloured header strip.
        # It is decoration, whereas a substantive illustration stays a figure.
        if any(intersects(b,box(im)) and not (inside(box(im),b,2) and im['bottom']-im['top']<h*.25 and im['x1']-im['x0']>w*.6) for im in content.images):continue
        if any(inside(box(line),b) and line['x1']-line['x0']>2 and line['bottom']-line['top']>2 for line in content.lines):continue
        # Dense arbitrary vector drawings are figures, not textual callouts.
        if sum(inside(box(c),b) for c in content.curves)>8:continue
        enclosed=text_lines(content.crop(b,strict=False),split_columns=False)
        candidates.append((b,enclosed))
    # Prefer the enclosing box over its coloured header strip / inner frame.
    candidates.sort(key=lambda item:-(item[0][2]-item[0][0])*(item[0][3]-item[0][1]))
    for b,enclosed in candidates:
        if any(inside(b,s['box']) for s in special):continue
        ordered=reading_order(enclosed);first=ordered[0];rest=ordered[1:]
        title=first['text'];body=paragraphs(rest)
        def callout(content):return '> **'+title+'**'+(('\n>\n'+ '\n'.join('> '+line if line else '>' for line in content.splitlines())) if content else '')
        special.append({'kind':'callout','box':list(b),'text':title+'\n'+body,'markdown':callout(body)})
    remaining=[line for line in lines if not any(inside(line['box'],s['box'],2) for s in special)]
    # Production filenames outside the text area are not textbook content.
    remaining=[l for l in remaining if not ((l['box'][1]<visible[1]+page.height*.05 or l['box'][3]>visible[3]-page.height*.05) and re.search(r'\.(?:indd|qxd)\b',l['text'],re.I))]
    ordered=reading_order(remaining+special);blocks=[];pending=[]
    def flush():
        if not pending:return
        text=paragraphs(pending);bounds=[min(l['box'][0] for l in pending),min(l['box'][1] for l in pending),max(l['box'][2] for l in pending),max(l['box'][3] for l in pending)]
        blocks.append({'kind':'text','box':bounds,'text':text,'markdown':text});pending.clear()
    for item in ordered:
        if item['kind']=='line':
            if pending and (item.get('baseline',item['box'][1])<pending[-1].get('baseline',pending[-1]['box'][1]) or item['box'][0]>pending[-1]['box'][2]+18 or item['box'][1]-pending[-1]['box'][3]>pending[-1]['size']*2.2):flush()
            pending.append(item)
        else:flush();blocks.append(item)
    flush()
    for block in blocks:
        b=block['box'];block['box']=[b[0]-visible[0],b[1]-visible[1],b[2]-visible[0],b[3]-visible[1]]
    return {'text':'\n\n'.join(b['text'] for b in blocks),'markdown':'\n\n'.join(b['markdown'] for b in blocks),'blocks':blocks,
            'layout_version':VERSION,'layout_size':[visible[2]-visible[0],visible[3]-visible[1]]}

def page_markdown(record,entries):
    blocks=record.get('blocks');size=record.get('layout_size')
    def image(e):return f"{e['label']} · PDF {e['page']}쪽 · 이미지 ID: `{e['id']}`\n\n![{e['label']}](images/{e['id']})"
    if not blocks or not size:return '\n\n'.join([record.get('markdown',record['text'])]+[image(e) for e in entries])
    figures=[[e['box'][0],size[1]-e['box'][3],e['box'][2],size[1]-e['box'][1]] for e in entries if e.get('box')]
    items=[dict(b) for b in blocks if not (b['kind']=='text' and any(inside(b['box'],f,2) for f in figures))]
    for e in entries:
        b=e.get('box')
        if not b:continue
        topbox=[b[0],size[1]-b[3],b[2],size[1]-b[1]]
        items.append({'kind':'figure','box':topbox,'markdown':image(e)})
    return '\n\n'.join(item['markdown'] for item in reading_order(items))+''.join('\n\n'+image(e) for e in entries if not e.get('box'))
