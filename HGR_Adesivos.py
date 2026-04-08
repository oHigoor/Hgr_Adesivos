import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import requests
from rembg import remove, new_session
from io import BytesIO
import time, os, sys, threading, random
from tkinter import filedialog, Canvas, messagebox, simpledialog

class HGRCursedStudioPro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HGR Studio PRO - Gerador de Adesivos")
        self.geometry("1240x850")
        
        ctk.set_appearance_mode("dark")
        self.cor_accent = "#00CED1"
        
        self.rembg_session = new_session()
        self.caminho_adesivos = self.obter_caminho_pasta()
        
        # Variáveis de Imagem e Zoom
        self.imagem_ia_base = None
        self.imagem_rembg_base = None
        self.edicao_canvas = None
        self.edicao_draw = None
        self.zoom_level = 1.0
        
        # Pilhas de histórico
        self.pilha_desfazer = []
        self.pilha_refazer = []
        self.limite_historico = 20

        # --- BACKGROUND CONFIG (Wallpaper) ---
        self.url_wallpaper = "https://images.alphacoders.com/838/838143.png" 
        self.setup_background()

        # Criamos o Tabview com fg_color="transparent" para o wallpaper aparecer
        self.tabview = ctk.CTkTabview(self, width=1150, height=750, 
                                      fg_color="transparent", 
                                      bg_color="transparent")
        self.tabview.pack(pady=20, padx=20, expand=True, fill="both")
        
        self.tab_ia = self.tabview.add("🖼️ Gerador de Adesivos")
        self.tab_rembg = self.tabview.add("✂️ Editor de Fundo")
        self.tab_galeria = self.tabview.add("🗂️ Galeria de Salvos")
        
        # Configurar transparência nas abas
        for tab in [self.tab_ia, self.tab_rembg, self.tab_galeria]:
            tab.configure(fg_color="transparent")

        self.configurar_aba_ia()
        self.configurar_aba_rembg()
        self.configurar_aba_galeria()

    def setup_background(self):
        """Aplica o wallpaper e garante que ele fique no fundo de tudo"""
        try:
            res = requests.get(self.url_wallpaper, timeout=10)
            img_data = Image.open(BytesIO(res.content))
            self.bg_image = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(1240, 850))
            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except: pass

    def obter_caminho_pasta(self):
        if getattr(sys, 'frozen', False): base = os.path.dirname(sys.executable)
        else: base = os.path.dirname(os.path.abspath(__file__))
        pasta = os.path.join(base, "HGR_Adesivos_Salvos")
        if not os.path.exists(pasta): os.makedirs(pasta)
        return pasta

    # ================= ABA 1: GERADOR =================
    def configurar_aba_ia(self):
        self.tab_ia.grid_columnconfigure(1, weight=1)
        # Frame do menu lateral com semi-transparência (cor escura mas deixa ver o fundo)
        self.frame_menu = ctk.CTkFrame(self.tab_ia, width=280, corner_radius=15, fg_color=("#333333", "#1A1A1A"))
        self.frame_menu.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        ctk.CTkLabel(self.frame_menu, text="GERADOR DE ADESIVOS", font=("Segoe UI", 16, "bold")).pack(pady=20)
        self.entry_prompt = ctk.CTkEntry(self.frame_menu, placeholder_text="Descreva o adesivo...", width=220)
        self.entry_prompt.pack(pady=10)

        self.btn_gerar = ctk.CTkButton(self.frame_menu, text="GERAR ARTE", command=self.iniciar_ia, fg_color=self.cor_accent, text_color="black")
        self.btn_gerar.pack(pady=20)

        self.btn_save_ia = ctk.CTkButton(self.frame_menu, text="SALVAR PNG", command=self.salvar_ia, state="disabled")
        self.btn_save_ia.pack(pady=10)

        self.preview_ia = ctk.CTkLabel(self.tab_ia, text="Sua arte aparecerá aqui...", fg_color="black", corner_radius=15)
        self.preview_ia.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def iniciar_ia(self):
        prompt = self.entry_prompt.get()
        if not prompt: return
        self.btn_gerar.configure(state="disabled")
        threading.Thread(target=self.thread_ia, args=(prompt,), daemon=True).start()

    def thread_ia(self, prompt):
        try:
            url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"
            res = requests.get(url, timeout=20)
            self.imagem_ia_base = Image.open(BytesIO(res.content)).convert("RGBA")
            img_tk = ctk.CTkImage(self.imagem_ia_base, size=(450, 450))
            self.after(0, lambda: self.preview_ia.configure(image=img_tk, text=""))
            self.after(0, lambda: self.btn_save_ia.configure(state="normal"))
        except: pass
        finally: self.after(0, lambda: self.btn_gerar.configure(state="normal"))

    def salvar_ia(self):
        if not self.imagem_ia_base: return
        nome = simpledialog.askstring("Salvar", "Nome do adesivo:")
        if not nome: nome = f"Adesivo_IA_{int(time.time())}"
        try:
            input_data = BytesIO()
            self.imagem_ia_base.save(input_data, format='PNG')
            output = remove(input_data.getvalue(), session=self.rembg_session, alpha_matting=True)
            final = Image.open(BytesIO(output)).convert("RGBA")
            path = os.path.join(self.caminho_adesivos, f"{nome}.png")
            final.save(path)
            self.atualizar_lista_galeria()
            messagebox.showinfo("Sucesso", "Adesivo salvo!")
        except: pass

    # ================= ABA 2: EDITOR (BORRACHA SINCRONIZADA) =================
    def configurar_aba_rembg(self):
        self.tab_rembg.grid_rowconfigure(1, weight=1)
        self.tab_rembg.grid_columnconfigure(0, weight=1)

        self.frame_top = ctk.CTkFrame(self.tab_rembg, height=75, fg_color=("#333333", "#1A1A1A"))
        self.frame_top.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        self.btn_abrir = ctk.CTkButton(self.frame_top, text="📁 ABRIR", command=self.carregar_imagem_pc, width=80)
        self.btn_abrir.pack(side="left", padx=5)

        self.btn_auto_rembg = ctk.CTkButton(self.frame_top, text="✨ AUTO-LIMPAR", command=self.remover_fundo_automatico_aba2, fg_color="#4B0082", width=110, state="disabled")
        self.btn_auto_rembg.pack(side="left", padx=5)

        self.btn_borda = ctk.CTkButton(self.frame_top, text="⚪ BORDA", command=self.aplicar_borda_adesivo, fg_color="#F0F0F0", text_color="black", width=80, state="disabled")
        self.btn_borda.pack(side="left", padx=5)

        ctk.CTkLabel(self.frame_top, text="Borracha:").pack(side="left", padx=5)
        self.slider_borracha = ctk.CTkSlider(self.frame_top, from_=2, to=80, width=100)
        self.slider_borracha.pack(side="left", padx=5)
        self.slider_borracha.set(20)

        self.btn_zoom_in = ctk.CTkButton(self.frame_top, text="🔍 +", width=35, command=lambda: self.ajustar_zoom(0.2))
        self.btn_zoom_in.pack(side="left", padx=2)
        self.btn_zoom_out = ctk.CTkButton(self.frame_top, text="🔍 -", width=35, command=lambda: self.ajustar_zoom(-0.2))
        self.btn_zoom_out.pack(side="left", padx=2)

        self.btn_desfazer = ctk.CTkButton(self.frame_top, text="↩", command=self.desfazer_limpeza, fg_color="#555555", width=40)
        self.btn_desfazer.pack(side="left", padx=2)
        self.btn_refazer = ctk.CTkButton(self.frame_top, text="↪", command=self.refazer_limpeza, fg_color="#555555", width=40)
        self.btn_refazer.pack(side="left", padx=2)
        
        self.btn_salvar_pc = ctk.CTkButton(self.frame_top, text="💾 SALVAR", command=self.salvar_limpeza_manual, fg_color="#2E8B57", width=100, state="disabled")
        self.btn_salvar_pc.pack(side="right", padx=10)

        self.canvas_edicao = Canvas(self.tab_rembg, bg="#111111", highlightthickness=0, cursor="none")
        self.canvas_edicao.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        # Sincronização da borracha
        self.canvas_edicao.bind("<B1-Motion>", self.processar_borracha_movimento)
        self.canvas_edicao.bind("<Button-1>", self.processar_borracha_clique)
        self.canvas_edicao.bind("<Motion>", self.desenhar_cursor_visual)

    def carregar_imagem_pc(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.jpg *.png *.jpeg *.webp")])
        if not path: return
        self.zoom_level = 1.0
        self.pilha_desfazer = []
        self.pilha_refazer = []
        threading.Thread(target=self.preparar_imagem_limpeza, args=(path,), daemon=True).start()

    def preparar_imagem_limpeza(self, path):
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((800, 600), Image.LANCZOS)
            self.edicao_canvas = img.copy()
            self.edicao_draw = ImageDraw.Draw(self.edicao_canvas)
            self.after(0, self.atualizar_canvas)
            self.after(0, lambda: [self.btn_salvar_pc.configure(state="normal"), self.btn_auto_rembg.configure(state="normal"), self.btn_borda.configure(state="normal")])
        except: pass

    def ajustar_zoom(self, delta):
        if not self.edicao_canvas: return
        nova_escala = self.zoom_level + delta
        if 0.5 <= nova_escala <= 5.0:
            self.zoom_level = nova_escala
            self.atualizar_canvas()

    def atualizar_canvas(self):
        if self.edicao_canvas:
            largura = int(self.edicao_canvas.width * self.zoom_level)
            altura = int(self.edicao_canvas.height * self.zoom_level)
            img_zoom = self.edicao_canvas.resize((largura, altura), Image.NEAREST)
            self.tk_img = ImageTk.PhotoImage(img_zoom)
            self.canvas_edicao.delete("img_bg")
            cx, cy = self.canvas_edicao.winfo_width()//2, self.canvas_edicao.winfo_height()//2
            self.canvas_edicao.create_image(cx, cy, image=self.tk_img, anchor="center", tags="img_bg")
            self.canvas_edicao.tag_lower("img_bg")

    def desenhar_cursor_visual(self, event):
        self.canvas_edicao.delete("cursor")
        r = (self.slider_borracha.get() * self.zoom_level)
        self.canvas_edicao.create_oval(event.x-r, event.y-r, event.x+r, event.y+r, outline=self.cor_accent, width=2, tags="cursor")

    def processar_borracha_clique(self, event):
        if self.edicao_canvas:
            self.pilha_desfazer.append(self.edicao_canvas.copy())
            self.pilha_refazer = []
            self.executar_apagamento(event)

    def processar_borracha_movimento(self, event):
        self.desenhar_cursor_visual(event)
        self.executar_apagamento(event)

    def executar_apagamento(self, event):
        if not self.edicao_canvas: return
        r = self.slider_borracha.get()
        cx, cy = self.canvas_edicao.winfo_width()//2, self.canvas_edicao.winfo_height()//2
        x = (event.x - (cx - (self.edicao_canvas.width * self.zoom_level) // 2)) / self.zoom_level
        y = (event.y - (cy - (self.edicao_canvas.height * self.zoom_level) // 2)) / self.zoom_level
        self.edicao_draw.ellipse([x-r, y-r, x+r, y+r], fill=(0,0,0,0))
        self.atualizar_canvas()

    def aplicar_borda_adesivo(self):
        if not self.edicao_canvas: return
        self.pilha_desfazer.append(self.edicao_canvas.copy())
        alpha = self.edicao_canvas.getchannel('A')
        mascara_borda = alpha.filter(ImageFilter.MaxFilter(13)) 
        borda_branca = Image.new("RGBA", self.edicao_canvas.size, (255, 255, 255, 255))
        final = Image.composite(borda_branca, Image.new("RGBA", self.edicao_canvas.size, (0,0,0,0)), mascara_borda)
        final.paste(self.edicao_canvas, (0,0), self.edicao_canvas)
        self.edicao_canvas = final
        self.edicao_draw = ImageDraw.Draw(self.edicao_canvas)
        self.atualizar_canvas()

    def remover_fundo_automatico_aba2(self):
        if self.edicao_canvas:
            self.pilha_desfazer.append(self.edicao_canvas.copy())
            threading.Thread(target=self.thread_rembg_aba2).start()

    def thread_rembg_aba2(self):
        try:
            input_io = BytesIO()
            self.edicao_canvas.save(input_io, format='PNG')
            output = remove(input_io.getvalue(), session=self.rembg_session, alpha_matting=True)
            self.edicao_canvas = Image.open(BytesIO(output)).convert("RGBA")
            self.edicao_draw = ImageDraw.Draw(self.edicao_canvas)
            self.after(0, self.atualizar_canvas)
        except: pass

    def desfazer_limpeza(self):
        if self.pilha_desfazer:
            self.pilha_refazer.append(self.edicao_canvas.copy())
            self.edicao_canvas = self.pilha_desfazer.pop()
            self.edicao_draw = ImageDraw.Draw(self.edicao_canvas)
            self.atualizar_canvas()

    def refazer_limpeza(self):
        if self.pilha_refazer:
            self.pilha_desfazer.append(self.edicao_canvas.copy())
            self.edicao_canvas = self.pilha_refazer.pop()
            self.edicao_draw = ImageDraw.Draw(self.edicao_canvas)
            self.atualizar_canvas()

    def salvar_limpeza_manual(self):
        if not self.edicao_canvas: return
        nome = simpledialog.askstring("Salvar", "Nome do arquivo:")
        if nome:
            path = os.path.join(self.caminho_adesivos, f"{nome}.png")
            self.edicao_canvas.save(path)
            self.atualizar_lista_galeria()
            messagebox.showinfo("Sucesso", "Salvo!")

    # ================= ABA 3: GALERIA =================
    def configurar_aba_galeria(self):
        self.tab_galeria.grid_columnconfigure(0, weight=1)
        self.tab_galeria.grid_rowconfigure(1, weight=1)
        self.btn_refresh = ctk.CTkButton(self.tab_galeria, text="🔄 ATUALIZAR GALERIA", command=self.atualizar_lista_galeria)
        self.btn_refresh.grid(row=0, column=0, padx=20, pady=10)
        self.scroll_galeria = ctk.CTkScrollableFrame(self.tab_galeria, width=1100, height=550, fg_color="transparent")
        self.scroll_galeria.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.atualizar_lista_galeria()

    def atualizar_lista_galeria(self):
        for widget in self.scroll_galeria.winfo_children(): widget.destroy()
        arquivos = [f for f in os.listdir(self.caminho_adesivos) if f.lower().endswith(".png")]
        arquivos.sort(key=lambda x: os.path.getmtime(os.path.join(self.caminho_adesivos, x)), reverse=True)
        for arq in arquivos:
            caminho = os.path.join(self.caminho_adesivos, arq)
            frame = ctk.CTkFrame(self.scroll_galeria, fg_color=("#333333", "#1A1A1A"))
            frame.pack(fill="x", padx=10, pady=5)
            try:
                img = Image.open(caminho)
                img.thumbnail((60, 60))
                ctk_img = ctk.CTkImage(img, size=(50, 50))
                ctk.CTkLabel(frame, image=ctk_img, text="").pack(side="left", padx=10)
            except: pass
            ctk.CTkLabel(frame, text=arq).pack(side="left", padx=10)
            ctk.CTkButton(frame, text="Excluir", fg_color="#8B0000", width=70, command=lambda p=caminho: self.excluir_arq(p)).pack(side="right", padx=5)
            ctk.CTkButton(frame, text="Renomear", width=70, command=lambda p=caminho, n=arq: self.renomear_arq(p, n)).pack(side="right", padx=5)
            ctk.CTkButton(frame, text="Abrir", width=70, command=lambda p=caminho: os.startfile(p)).pack(side="right", padx=5)

    def renomear_arq(self, antigo, nome):
        novo = simpledialog.askstring("Renomear", f"Novo nome para {nome}:")
        if novo:
            if not novo.lower().endswith(".png"): novo += ".png"
            os.rename(antigo, os.path.join(self.caminho_adesivos, novo))
            self.atualizar_lista_galeria()

    def excluir_arq(self, caminho):
        if messagebox.askyesno("Excluir", "Apagar adesivo?"):
            os.remove(caminho)
            self.atualizar_lista_galeria()

if __name__ == "__main__":
    app = HGRCursedStudioPro()
    app.mainloop()