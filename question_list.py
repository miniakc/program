"""Original-style question rows with real independent checkboxes."""
import tkinter as tk
from tkinter import ttk
from review import status_label

class QuestionList(ttk.Frame):
    def __init__(self,parent,on_edit,on_change):
        super().__init__(parent);self.rows={};self.checked=set();self.active=None;self.on_edit=on_edit;self.on_change=on_change
        self.canvas=tk.Canvas(self,bg='white',highlightthickness=1,highlightbackground='#e2eae7');scroll=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview);scroll.pack(side='right',fill='y');self.canvas.pack(fill='both',expand=True);self.canvas.configure(yscrollcommand=scroll.set)
        self.body=ttk.Frame(self.canvas,style='Card.TFrame');self.item=self.canvas.create_window((0,0),window=self.body,anchor='nw')
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.item,width=e.width));self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.bind_all('<MouseWheel>',self.wheel,add='+')
    def wheel(self,e):
        target=self.winfo_containing(e.x_root,e.y_root)
        if target and str(target).startswith(str(self)):self.canvas.yview_scroll(-int(e.delta/120),'units')
    def get_children(self):return tuple(self.rows)
    def selection(self):return tuple(id for id in self.rows if id in self.checked)
    def selection_set(self,ids):
        if isinstance(ids,str):ids=[ids]
        self.checked=set(ids)&set(self.rows)
        for id,row in self.rows.items():row['var'].set(id in self.checked)
        self.on_change()
    def see(self,id):
        if id in self.rows:
            self.update_idletasks();self.canvas.yview_moveto(self.rows[id]['host'].winfo_y()/max(self.body.winfo_height(),1))
    def delete(self,*ids):
        for id in ids:
            if id in self.rows:self.rows.pop(id)['host'].destroy();self.checked.discard(id)
    def add_question(self,q,location):
        id=q['id'];host=tk.Frame(self.body,bg='white',highlightbackground='#e2eae7',highlightthickness=1,padx=12,pady=13);host.pack(fill='x')
        var=tk.BooleanVar(value=id in self.checked)
        def toggle():
            if var.get():self.checked.add(id)
            else:self.checked.discard(id)
            self.active=id;self.on_change()
        cb=ttk.Checkbutton(host,variable=var,command=toggle);cb.grid(row=0,column=0,rowspan=3,sticky='n',padx=(0,9))
        host.columnconfigure(1,weight=1)
        title=tk.Label(host,text=q['stem'],bg='white',fg='#20343e',font=('맑은 고딕',11,'bold'),justify='left',anchor='w',wraplength=500);title.grid(row=0,column=1,sticky='ew',padx=(0,10))
        concept=tk.Label(host,text='학습목표 · '+q['concept'],bg='white',fg='#618471',font=('맑은 고딕',9),anchor='w',justify='left',wraplength=500);concept.grid(row=1,column=1,sticky='ew',pady=4)
        source=tk.Label(host,text=location,bg='white',fg='#8b9c94',font=('맑은 고딕',9),anchor='w',justify='left',wraplength=500);source.grid(row=2,column=1,sticky='ew')
        side=tk.Frame(host,bg='white');side.grid(row=0,column=2,rowspan=3,sticky='ne')
        tk.Label(side,text=q.get('type','객관식'),bg='#f0f4f2',fg='#6d8176',font=('맑은 고딕',9),padx=8,pady=3).pack(anchor='e')
        tk.Label(side,text=status_label(q),bg='#e5f3ec' if q.get('approved') else '#fcf1df',fg='#398766' if q.get('approved') else '#9b7c42',font=('맑은 고딕',9),padx=8,pady=3).pack(anchor='e',pady=5)
        ttk.Button(side,text='검토·수정',command=lambda:self.on_edit(q)).pack(anchor='e')
        def resize(e):
            width=max(150,e.width-190)
            for w in (title,concept,source):w.configure(wraplength=width)
        host.bind('<Configure>',resize)
        for w in (host,title,concept,source):w.bind('<Double-1>',lambda e:self.on_edit(q))
        self.rows[id]={'host':host,'var':var,'checkbutton':cb,'question':q}
