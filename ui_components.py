import tkinter as tk
from tkinter import ttk

class RoundedPanel(tk.Canvas):
    def __init__(self,parent,padding=18,**pack):
        super().__init__(parent,bg='#f6f8f8',highlightthickness=0,height=80)
        self.pack(**pack);self.padding=padding
        self.shape=self.create_polygon(0,0,1,1,fill='white',outline='#e2eae7',smooth=True)
        self.inner=ttk.Frame(self,style='Card.TFrame',padding=padding)
        self.window=self.create_window((6,6),window=self.inner,anchor='nw')
        self.bind('<Configure>',self.layout);self.inner.bind('<Configure>',self.height_changed)
    def height_changed(self,event):
        height=self.inner.winfo_reqheight()+12
        if int(self.cget('height'))!=height:self.configure(height=height)
    def layout(self,event):
        w=max(event.width,20);h=max(event.height,20);r=14
        self.coords(self.shape,r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1)
        self.itemconfigure(self.window,width=w-12)
