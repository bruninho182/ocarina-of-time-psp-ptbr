"""Interface Windows para o patcher de Ocarina of Time PSP em PT-BR."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from aplicar_ptbr import patch, prepare_roms


def main():
    window = tk.Tk()
    window.title("Ocarina of Time PSP · PT-BR")
    window.minsize(670, 275)
    window.configure(background="#12271c")
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure("TFrame", background="#12271c")
    style.configure("TLabel", background="#12271c", foreground="#e9f2e8")
    style.configure("Title.TLabel", foreground="#f0ce79", font=("Segoe UI", 16, "bold"))
    style.configure("TEntry", fieldbackground="#203d2d", foreground="#ffffff",
                    insertcolor="#ffffff", bordercolor="#55705b", padding=6)
    style.map("TEntry", bordercolor=[("focus", "#f0ce79")])
    style.configure("TButton", background="#29553b", foreground="#ffffff",
                    bordercolor="#55705b", padding=(10, 6))
    style.map("TButton", background=[("disabled", "#293e32"), ("active", "#36714e")],
              foreground=[("disabled", "#b9c7bb")])
    style.configure("Apply.TButton", background="#e7c36b", foreground="#17281d")
    style.map("Apply.TButton", background=[("disabled", "#293e32"), ("active", "#f4d689")],
              foreground=[("disabled", "#b9c7bb")])
    style.configure("Credit.TButton", foreground="#f0ce79")
    frame = ttk.Frame(window, padding=20)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="Aplicar tradução ao port de PSP 1.0", style="Title.TLabel").grid(sticky="w")
    ttk.Label(frame, text="Use uma cópia do port que já tenha iniciado em inglês.").grid(sticky="w", pady=(2, 12))

    fields = []
    labels = ("ROM original USA NTSC 1.0 (.z64)", "ROM Redux T1.8 em PT-BR (.z64)",
              "Pasta do port com EBOOT.PBP", "Pasta onde salvar o resultado")
    for index, label in enumerate(labels):
        value = tk.StringVar()
        fields.append(value)
        row = 2 + 2 * index
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=value).grid(row=row + 1, column=0, sticky="ew", pady=(0, 6))

        def browse(field=value, directory=index >= 2):
            if directory:
                selected = filedialog.askdirectory(parent=window, mustexist=True)
            else:
                selected = filedialog.askopenfilename(parent=window, filetypes=[("ROM de Nintendo 64", "*.z64")])
            if selected:
                field.set(selected)

        ttk.Button(frame, text="Selecionar…", command=browse).grid(row=row + 1, column=1, padx=(8, 0))

    def apply():
        values = [field.get().strip() for field in fields]
        if not all(values):
            messagebox.showerror("Campos obrigatórios", "Selecione as duas ROMs e as duas pastas.", parent=window)
            return
        clean, redux, port, destination = map(Path, values)
        output = destination / "saida-ptbr"
        status.set("Validando arquivos e gerando a tradução…")
        button.state(["disabled"])
        window.update_idletasks()
        try:
            original, translated = prepare_roms(clean.read_bytes(), redux.read_bytes())
            patch(port, output, original, translated)
        except (OSError, ValueError) as error:
            status.set("Confira os arquivos e tente novamente.")
            messagebox.showerror("Falha ao aplicar", str(error), parent=window)
        else:
            status.set("Arquivos gerados com sucesso.")
            messagebox.showinfo(
                "Tradução gerada",
                f"Arquivos salvos em:\n{output}\n\n"
                "Faça backup dos arquivos do PSP. Depois copie o EBOOT.PBP e a pasta data "
                "da saída para a pasta do jogo, mantendo seus caminhos.",
                parent=window,
            )
        finally:
            button.state(["!disabled"])

    status = tk.StringVar()
    ttk.Label(frame, textvariable=status).grid(row=10, column=0, sticky="w")
    button = ttk.Button(frame, text="Gerar arquivos PT-BR", command=apply, style="Apply.TButton")
    button.grid(row=10, column=1, pady=(8, 0), sticky="e")
    ttk.Button(
        frame,
        text="Adaptação para PSP por Bruno Patrick Ferreira · GitHub",
        command=lambda: webbrowser.open("https://github.com/bruninho182"),
        cursor="hand2",
        style="Credit.TButton",
    ).grid(row=11, column=0, columnspan=2, pady=(12, 0), sticky="w")
    window.mainloop()


if __name__ == "__main__":
    main()
