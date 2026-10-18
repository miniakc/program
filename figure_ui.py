"""Local crop editor for scans and complex PDF figure layouts."""
import json,tkinter as tk
from tkinter import ttk,messagebox
from PIL import ImageTk
import pypdfium2 as pdfium
from figure_engine import detect_regions,clip,area

class FigureRegionEditor(tk.Toplevel):
    def __init__(self,parent,path,assets,digest,on_save):
        super().__init__(parent);self.title('그림 확인 · 영역 선택');self.geometry(f'{min(960,self.winfo_screenwidth()-60)}x{min(730,self.winfo_screenheight()-90)}+20+20');self.transient(parent);self.grab_set();self.document=pdfium.PdfDocument(str(path));self.on_save=on_save;self.assets=assets;self.digest=digest
        self.configure(bg='#f6f8f8');self.boxes=[];self.drag=None;self.page_no=tk.IntVar(value=1)
        top=ttk.Frame(self,padding=14);top.pack(fill='x');ttk.Label(top,text='그림과 겹친 설명·라벨을 함께 선택하세요.',font=('맑은 고딕',14,'bold')).pack(anchor='w')
        row=ttk.Frame(top);row.pack(fill='x',pady=8);ttk.Label(row,text='PDF 페이지').pack(side='left');self.pick=ttk.Combobox(row,values=list(range(1,len(self.document)+1)),state='readonly',width=7,textvariable=self.page_no);self.pick.pack(side='left',padx=8);self.pick.bind('<<ComboboxSelected>>',lambda e:self.show_page())
        ttk.Label(row,text='마우스로 드래그해서 그림 영역을 추가합니다. 본문은 제외하세요.').pack(side='left')
        self.info=ttk.Label(top,text='');self.info.pack(anchor='w')
        bottom=ttk.Frame(self,padding=14);bottom.pack(side='bottom',fill='x')
        ttk.Button(bottom,text='닫기',command=self.close).pack(side='right');ttk.Button(bottom,text='이 페이지 영역 저장',style='Primary.TButton',command=self.save).pack(side='right',padx=8)
        ttk.Button(bottom,text='마지막 영역 취소',command=self.undo).pack(side='left');ttk.Button(bottom,text='이 페이지 그림 없음',command=self.clear).pack(side='left',padx=8)
        self.canvas=tk.Canvas(self,bg='#e6ece9',highlightthickness=0);self.canvas.pack(fill='both',expand=True,padx=14,pady=(0,12));self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.protocol('WM_DELETE_WINDOW',self.close);self.after_idle(self.show_page)
    def show_page(self):
        page=self.document[self.page_no.get()-1]
        try:
            self.w,self.h=page.get_size();self.scale=min(max(self.canvas.winfo_width()-20,500)/self.w,max(self.canvas.winfo_height()-20,300)/self.h)
            bitmap=page.render(scale=self.scale)
            try:self.photo=ImageTk.PhotoImage(bitmap.to_pil().copy())
            finally:bitmap.close()
            p=self.assets.root/(self.digest+'.regions.json');data=json.loads(p.read_text()) if p.exists() else {}
            self.boxes=data.get(str(self.page_no.get()),detect_regions(page)[0])
        finally:page.close()
        self.redraw()
    def redraw(self):
        self.canvas.delete('all');self.canvas.create_image(10,10,image=self.photo,anchor='nw')
        for i,b in enumerate(self.boxes,1):
            x0,y0,x1,y1=self.to_canvas(b);self.canvas.create_rectangle(x0,y0,x1,y1,outline='#0c8476',width=2);self.canvas.create_text(x0+4,y0+4,text=str(i),anchor='nw',fill='#064e45',font=('맑은 고딕',12,'bold'))
        self.info.configure(text=f'선택 영역 {len(self.boxes)}개 · 겹쳐진 텍스트·화살표는 그림에 포함 · 전체 페이지는 저장하지 않습니다.')
    def to_canvas(self,b):return (10+b[0]*self.scale,10+(self.h-b[3])*self.scale,10+b[2]*self.scale,10+(self.h-b[1])*self.scale)
    def press(self,e):self.drag=(e.x,e.y)
    def motion(self,e):
        self.canvas.delete('drag')
        if self.drag:self.canvas.create_rectangle(*self.drag,e.x,e.y,outline='#bd6e41',width=2,tags='drag')
    def release(self,e):
        if not self.drag:return
        x,y=self.drag;self.drag=None
        b=clip(((min(x,e.x)-10)/self.scale,self.h-(max(y,e.y)-10)/self.scale,(max(x,e.x)-10)/self.scale,self.h-(min(y,e.y)-10)/self.scale),self.w,self.h)
        if area(b)>self.w*self.h*.9:messagebox.showinfo('그림 영역 선택','페이지 전체 대신 그림 영역만 선택하세요.',parent=self)
        elif b[2]-b[0]>=10 and b[3]-b[1]>=10:self.boxes.append(b)
        self.redraw()
    def clear(self):self.boxes=[];self.redraw()
    def undo(self):
        if self.boxes:self.boxes.pop();self.redraw()
    def save(self):
        page=self.page_no.get();boxes=list(self.boxes);self.close();self.on_save(page,boxes)
    def close(self):self.document.close();self.destroy()
