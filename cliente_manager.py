import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

try:
    import requests
except ImportError:  # pragma: no cover - depende do ambiente
    requests = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_DISPONIVEL = True
except ImportError:  # pragma: no cover - depende do ambiente
    A4 = None
    SimpleDocTemplate = None
    Paragraph = None
    getSampleStyleSheet = None
    REPORTLAB_DISPONIVEL = False

from database import Database


def _formatar_valor(valor):
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0,00"


def _maiusc(valor):
    """Converte texto para maiúsculo com segurança (aceita None, número etc.)."""
    if valor is None:
        return ""
    return str(valor).upper()


def _vincular_maiusculas_entry(entry):
    """Faz um campo Entry converter automaticamente para maiúsculas tudo o que
    for digitado ou colado, em tempo real, sem perder a posição do cursor."""
    def _forcar(event=None):
        texto = entry.get()
        maiusculo = texto.upper()
        if texto != maiusculo:
            pos = entry.index(tk.INSERT)
            entry.delete(0, tk.END)
            entry.insert(0, maiusculo)
            entry.icursor(pos)
    entry.bind("<KeyRelease>", _forcar)
    entry.bind("<<Paste>>", lambda e: entry.after(1, _forcar))
    return entry


def _vincular_maiusculas_texto(text_widget):
    """Mesma ideia do Entry, mas para campos de texto (Text) com várias linhas."""
    def _forcar(event=None):
        texto = text_widget.get("1.0", tk.END)
        maiusculo = texto.upper()
        if texto != maiusculo:
            pos = text_widget.index(tk.INSERT)
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", maiusculo)
            text_widget.mark_set(tk.INSERT, pos)
    text_widget.bind("<KeyRelease>", _forcar)
    text_widget.bind("<<Paste>>", lambda e: text_widget.after(1, _forcar))
    return text_widget


def _maiusculizar_cliente(cliente):
    """Garante que os dados de texto livre do cliente fiquem em maiúsculo -
    inclusive dados antigos, cadastrados antes desta melhoria existir."""
    cliente = dict(cliente or {})
    cliente["nome"] = _maiusc(cliente.get("nome", ""))
    cliente["cpf"] = _maiusc(cliente.get("cpf", ""))
    cliente["cnpj"] = _maiusc(cliente.get("cnpj", ""))
    cliente["telefone"] = _maiusc(cliente.get("telefone", ""))
    cliente["email"] = _maiusc(cliente.get("email", ""))
    endereco = cliente.get("endereco") or {}
    if isinstance(endereco, dict):
        cliente["endereco"] = {
            chave: (_maiusc(valor) if isinstance(valor, str) else valor)
            for chave, valor in endereco.items()
        }
    return cliente


def _maiusculizar_tecnico(tecnico):
    tecnico = dict(tecnico or {})
    tecnico["nome"] = _maiusc(tecnico.get("nome", ""))
    tecnico["telefone"] = _maiusc(tecnico.get("telefone", ""))
    tecnico["especialidade"] = _maiusc(tecnico.get("especialidade", ""))
    return tecnico


def _maiusculizar_os(os_item):
    """Idem, para os campos de texto livre de uma Ordem de Serviço.
    Situação, id, datas e valores de serviço ficam de fora de propósito:
    situação vem de uma lista fixa de opções (não é texto digitado), e
    id/datas/valores não são texto - maiusculizá-los não faz sentido."""
    os_item = dict(os_item or {})
    equipamento = os_item.get("equipamento") or {}
    if isinstance(equipamento, dict):
        os_item["equipamento"] = {
            chave: (_maiusc(valor) if isinstance(valor, str) else valor)
            for chave, valor in equipamento.items()
        }
    os_item["acessorios"] = _maiusc(os_item.get("acessorios", ""))
    os_item["defeito"] = _maiusc(os_item.get("defeito", ""))
    os_item["obs_gerais"] = _maiusc(os_item.get("obs_gerais", ""))
    os_item["obs_tecnico"] = _maiusc(os_item.get("obs_tecnico", ""))

    cliente = os_item.get("cliente")
    if isinstance(cliente, dict) and cliente:
        os_item["cliente"] = _maiusculizar_cliente(cliente)

    tecnico = os_item.get("tecnico")
    if isinstance(tecnico, dict):
        os_item["tecnico"] = _maiusculizar_tecnico(tecnico)
    elif isinstance(tecnico, str) and tecnico:
        os_item["tecnico"] = _maiusc(tecnico)

    return os_item


def obter_pasta_documentos():
    """Retorna o caminho da pasta Documentos do usuário no Windows (respeitando
    até pasta Documentos redirecionada para o OneDrive). Em outros sistemas
    operacionais, usa a pasta 'Documents' dentro da pasta pessoal do usuário."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            CSIDL_PERSONAL = 5  # "Minha pasta Documentos"
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
            if buf.value:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def formatar_os_para_lista(os_item):
    cliente = os_item.get("cliente", {}) or {}
    nome_cliente = cliente.get("nome", "Sem cliente")
    equipamento = os_item.get("equipamento", {}) or {}
    marca = equipamento.get("Marca", "")
    modelo = equipamento.get("Modelo", "")
    serie = equipamento.get("Número de Série", "")
    detalhes_equipamento = " / ".join([part for part in [marca, modelo, serie] if part]) or "Sem equipamento"
    tecnico = os_item.get("tecnico", "") or ""
    tecnico_nome = tecnico.get("nome", "") if isinstance(tecnico, dict) else str(tecnico or "")
    situacao = os_item.get("situacao", "Sem situação")
    return f"OS {os_item['id']:06d} | {os_item.get('data', '-')} | {nome_cliente} | {situacao} | R$ {_formatar_valor(os_item.get('total', 0))} | {detalhes_equipamento} | Técnico: {tecnico_nome or '-'}"


def buscar_ordens(ordens, termo):
    termo = (termo or "").strip().lower()
    if not termo:
        return sorted(ordens, key=lambda item: item.get("id", 0), reverse=True)

    resultados = []
    for os_item in ordens:
        cliente = os_item.get("cliente", {}) or {}
        equipamento = os_item.get("equipamento", {}) or {}
        tecnico = os_item.get("tecnico", "") or ""
        tecnico_nome = tecnico.get("nome", "") if isinstance(tecnico, dict) else str(tecnico or "")
        texto_base = " ".join([
            str(os_item.get("id", "")),
            str(os_item.get("data", "")),
            str(os_item.get("situacao", "")),
            str(cliente.get("nome", "")),
            str(cliente.get("cpf", "")),
            str(cliente.get("cnpj", "")),
            str(equipamento.get("Marca", "")),
            str(equipamento.get("Modelo", "")),
            str(equipamento.get("Número de Série", "")),
            str(os_item.get("defeito", "")),
            str(os_item.get("acessorios", "")),
            tecnico_nome,
        ]).lower()
        if termo in texto_base:
            resultados.append(os_item)
    return sorted(resultados, key=lambda item: item.get("id", 0), reverse=True)


def montar_resumo_os(os_item):
    cliente = os_item.get("cliente", {}) or {}
    equipamento = os_item.get("equipamento", {}) or {}
    tecnico = os_item.get("tecnico", "") or ""
    tecnico_nome = tecnico.get("nome", "") if isinstance(tecnico, dict) else str(tecnico or "")
    detalhes_equipamento = " / ".join([part for part in [equipamento.get("Marca", ""), equipamento.get("Modelo", ""), equipamento.get("Número de Série", "")] if part]) or "Não informado"
    servicos = os_item.get("servicos", {}) or {}
    valores = [f"{chave}: R$ {_formatar_valor(valor)}" for chave, valor in servicos.items() if valor]
    resumo = [
        f"O.S. nº {os_item.get('id', '-')}",
        f"Cliente: {cliente.get('nome', 'Sem cliente')}",
        f"CPF/CNPJ: {cliente.get('cpf', '') or cliente.get('cnpj', '') or '-'}",
        f"Equipamento: {detalhes_equipamento}",
        f"Situação: {os_item.get('situacao', 'Sem situação')}",
        f"Técnico: {tecnico_nome or '-'}",
        f"Total: R$ {_formatar_valor(os_item.get('total', 0))}",
        f"Entrada: {os_item.get('data_entrada', '-') or '-'}",
        f"Saída: {os_item.get('data_saida', '-') or '-'}",
    ]
    if valores:
        resumo.append("Valores: " + " | ".join(valores))
    resumo.append(f"Defeito: {os_item.get('defeito', '-') or '-'}")
    resumo.append(f"Acessórios: {os_item.get('acessorios', '-') or '-'}")
    resumo.append(f"Observações: {os_item.get('obs_gerais', os_item.get('obs_tecnico', '-')) or '-'}")
    return "\n".join(resumo)


class OrdemServicoApp:
    # Ordem "natural" do fluxo de atendimento, usada tanto no combobox de Situação
    # quanto na ordenação por fluxo da coluna Situação na tela inicial.
    SITUACOES_FLUXO = [
        "Aguardando autorização do orçamento",
        "Em reparo",
        "Pronto",
        "Sem reparo",
        "Encerrada",
        "Cancelada",
    ]

    def __init__(self):
        self.db = Database()
        self.ordens = [_maiusculizar_os(o) for o in self.db.carregar_ordens()]
        self.clientes = [_maiusculizar_cliente(c) for c in self.db.carregar_clientes()]
        self.os_atual = self.criar_nova_os()
        self.tecnicos = [_maiusculizar_tecnico(t) for t in self.db.carregar_tecnicos()]
        # Garante que dados cadastrados antes desta melhoria (ainda em
        # minúsculo/misto no banco) também fiquem salvos em maiúsculo daqui pra frente.
        self.db.salvar_clientes(self.clientes)
        self.db.salvar_tecnicos(self.tecnicos)
        self.db.salvar_ordens(self.ordens)
        self.filtro_inicial_atual = ""
        # Ciclo de ordenação da coluna "Situação": 0=fluxo ↑, 1=fluxo ↓, 2=A-Z, 3=Z-A
        # Começa em -1 para que o primeiro clique caia no modo 0 (fluxo crescente),
        # do mesmo jeito que o primeiro clique nas outras colunas começa em ordem crescente.
        self.situacao_modo_ordenacao = -1

        self.root = tk.Tk()
        self.root.title("Ordem de Serviço - Assistência Técnica")
        self.root.geometry("1400x820")
        self.root.configure(bg="#f0f0f0")

        self.inicio_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.main_frame = tk.Frame(self.root, bg="#f0f0f0")

        self.criar_tela_inicial()
        self.criar_cabecalho()
        self.criar_area_cliente()
        self.criar_area_equipamento()
        self.criar_area_servicos()

        self.main_frame.pack_forget()
        self.inicio_frame.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.sair)
        self.root.mainloop()

    def criar_tela_inicial(self):
        titulo = tk.Label(self.inicio_frame, text="Lista de Ordens de Serviço", font=("Arial", 24, "bold"), bg="#f0f0f0")
        titulo.pack(pady=(20, 5))

        descricao = tk.Label(
            self.inicio_frame,
            text="Selecione uma O.S. para carregar ou inicie uma nova ordem.",
            font=("Arial", 14),
            bg="#f0f0f0"
        )
        descricao.pack(pady=(0, 15))

        busca_frame = tk.Frame(self.inicio_frame, bg="#f0f0f0")
        busca_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(busca_frame, text="Buscar O.S./Cliente/CPF/CNPJ:", font=("Arial", 11), bg="#f0f0f0").grid(row=0, column=0, sticky="w")
        self.entry_busca_inicial = tk.Entry(busca_frame, width=45)
        self.entry_busca_inicial.grid(row=0, column=1, padx=8)
        tk.Button(busca_frame, text="Buscar", width=12, command=self.filtrar_os_inicial).grid(row=0, column=2, padx=4)
        tk.Button(busca_frame, text="Limpar", width=12, command=self.limpar_busca_inicial).grid(row=0, column=3, padx=4)

        frame_lista = tk.Frame(self.inicio_frame, bg="#f0f0f0")
        frame_lista.pack(fill="both", expand=True, padx=20, pady=10)

        colunas = ["OS", "Cliente", "CPF / CNPJ", "Situação", "Entrada", "Saída"]
        self.tree_inicial = ttk.Treeview(frame_lista, columns=colunas, show="headings", height=14)
        self.ordenacao_inicial = {coluna: False for coluna in colunas}
        larguras_colunas = {"OS": 110, "Cliente": 260, "CPF / CNPJ": 140, "Situação": 190, "Entrada": 130, "Saída": 130}
        for coluna in colunas:
            largura = larguras_colunas.get(coluna, 130)
            self.tree_inicial.heading(coluna, text=coluna, command=lambda c=coluna: self.ordenar_coluna_inicial(c))
            self.tree_inicial.column(coluna, width=largura, anchor="w")

        scrollbar = ttk.Scrollbar(frame_lista, orient="vertical", command=self.tree_inicial.yview)
        self.tree_inicial.configure(yscrollcommand=scrollbar.set)
        self.tree_inicial.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree_inicial.bind("<Double-1>", self.on_tree_duplo_clique)

        botoes = tk.Frame(self.inicio_frame, bg="#f0f0f0")
        botoes.pack(pady=10)

        tk.Button(botoes, text="Carregar O.S. Selecionada", bg="#2196F3", fg="white", font=("Arial", 12, "bold"), width=22, command=self.carregar_os_selecionada_inicial).pack(side="left", padx=8)
        tk.Button(botoes, text="Nova O.S.", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=18, command=self.abrir_tela_os).pack(side="left", padx=8)
        tk.Button(botoes, text="Ver Fechadas / Abertas", bg="#FF9800", fg="white", font=("Arial", 12, "bold"), width=18, command=self.mostrar_os_fechadas).pack(side="left", padx=8)
        tk.Button(botoes, text="Sair", bg="#f44336", fg="white", font=("Arial", 12, "bold"), width=18, command=self.sair).pack(side="left", padx=8)

        self.mostrar_fechadas_flag = False
        self.atualizar_lista_inicial()
        # Mostra a seta indicando que a lista inicia ordenada por O.S. (mais recente primeiro)
        self._atualizar_cabecalhos_ordenacao("OS")

    def abrir_tela_os(self):
        self.inicio_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)

    def voltar_para_inicial(self):
        if self.main_frame.winfo_ismapped():
            self.main_frame.pack_forget()
            self.inicio_frame.pack(fill="both", expand=True)

    def atualizar_lista_inicial(self, resultados=None):
        for item in self.tree_inicial.get_children():
            self.tree_inicial.delete(item)

        # Quando 'resultados' já vem pronto (de uma busca ou de um clique no cabeçalho
        # de ordenação), a ordem dele deve ser respeitada. Antes, esta função reordenava
        # tudo por ID de novo aqui dentro, o que anulava qualquer ordenação escolhida
        # pelo usuário — por isso clicar no cabeçalho parecia não fazer nada.
        if resultados is not None:
            ordens = resultados
        else:
            ordens = sorted(self.ordens, key=lambda item: item.get("id", 0), reverse=True)
        
        # Aplicar filtro de abertas/fechadas em qualquer caso
        situacoes_fechadas = ["Sem reparo", "Cancelada", "Encerrada"]
        if self.mostrar_fechadas_flag:
            # Mostrar apenas fechadas
            ordens = [o for o in ordens if o.get("situacao", "") in situacoes_fechadas]
        else:
            # Mostrar apenas abertas (padrão)
            ordens = [o for o in ordens if o.get("situacao", "") not in situacoes_fechadas]

        for os_item in ordens:
            cliente = os_item.get("cliente", {}) or {}
            cpf = str(cliente.get("cpf", ""))
            cnpj = str(cliente.get("cnpj", ""))
            cpf_cnpj = cpf if cpf else (cnpj if cnpj else "-")
            self.tree_inicial.insert(
                "",
                tk.END,
                values=(
                    str(os_item.get("id", "")).zfill(6),
                    cliente.get("nome", "Sem cliente"),
                    cpf_cnpj,
                    os_item.get("situacao", ""),
                    os_item.get("data_entrada", ""),
                    os_item.get("data_saida", "")
                )
            )

    def ordenar_coluna_inicial(self, coluna):
        # Respeita o filtro de busca atualmente aplicado na tela inicial, em vez de
        # sempre reordenar a lista completa (o que descartava a busca feita pelo usuário).
        base = buscar_ordens(self.ordens, self.filtro_inicial_atual)

        if coluna == "Situação":
            # A coluna Situação alterna entre as duas formas de agrupar pedidas:
            # 0 = fluxo de atendimento crescente, 1 = fluxo decrescente,
            # 2 = alfabética A-Z, 3 = alfabética Z-A — depois volta ao início.
            self.situacao_modo_ordenacao = (self.situacao_modo_ordenacao + 1) % 4
            modo = self.situacao_modo_ordenacao
            if modo in (0, 1):
                ordenado = sorted(base, key=lambda o: self._chave_situacao_fluxo(o.get("situacao", "")), reverse=(modo == 1))
            else:
                ordenado = sorted(base, key=lambda o: str(o.get("situacao", "")).lower(), reverse=(modo == 3))
        else:
            self.ordenacao_inicial[coluna] = not self.ordenacao_inicial[coluna]
            reverse = not self.ordenacao_inicial[coluna]

            if coluna == "OS":
                ordenado = sorted(base, key=lambda o: int(o.get("id", 0)), reverse=reverse)
            elif coluna == "Cliente":
                ordenado = sorted(base, key=lambda o: str(o.get("cliente", {}).get("nome", "")).lower(), reverse=reverse)
            elif coluna == "CPF / CNPJ":
                def _limpar_cpf_cnpj(valor):
                    return int(''.join(ch for ch in valor if ch.isdigit())) if valor and any(ch.isdigit() for ch in valor) else 0
                ordenado = sorted(base, key=lambda o: _limpar_cpf_cnpj((o.get("cliente", {}) or {}).get("cpf", "") or (o.get("cliente", {}) or {}).get("cnpj", "")), reverse=reverse)
            elif coluna in {"Entrada", "Saída"}:
                ordenado = sorted(base, key=lambda o: self._parse_data(o.get("data_entrada" if coluna == "Entrada" else "data_saida", "")), reverse=reverse)
            else:
                ordenado = base

        self._atualizar_cabecalhos_ordenacao(coluna)
        self.atualizar_lista_inicial(ordenado)

    def _chave_situacao_fluxo(self, situacao):
        situacao = situacao or ""
        try:
            # Situações conhecidas seguem a posição no fluxo de atendimento.
            return (0, self.SITUACOES_FLUXO.index(situacao))
        except ValueError:
            # Situações não previstas na lista (ex.: digitadas manualmente em O.S. antigas)
            # vão para o final, ordenadas alfabeticamente entre si.
            return (1, situacao.lower())

    def _atualizar_cabecalhos_ordenacao(self, coluna_ordenada):
        rotulos_situacao = {
            0: "▼ Situação (fluxo)",
            1: "▲ Situação (fluxo)",
            2: "▼ Situação (A-Z)",
            3: "▲ Situação (A-Z)",
        }
        for coluna in self.ordenacao_inicial:
            if coluna == "Situação":
                texto = rotulos_situacao[self.situacao_modo_ordenacao] if coluna_ordenada == "Situação" else "Situação"
            else:
                prefixo = ""
                if coluna == coluna_ordenada:
                    # A seta fica no INÍCIO do texto de propósito: se ficasse no final, ela cairia
                    # perto da borda direita da coluna, onde o Tkinter usa o clique para
                    # redimensionar em vez de clicar no cabeçalho — por isso o clique "não fazia nada".
                    prefixo = "▲ " if self.ordenacao_inicial[coluna] else "▼ "
                texto = prefixo + coluna
            self.tree_inicial.heading(coluna, text=texto, command=lambda c=coluna: self.ordenar_coluna_inicial(c))

    def _limpar_cpf(self, cpf):
        return int(''.join(ch for ch in cpf if ch.isdigit())) if cpf and any(ch.isdigit() for ch in cpf) else 0

    def _parse_data(self, data_text):
        try:
            return datetime.strptime(data_text, "%d/%m/%Y %H:%M")
        except Exception:
            try:
                return datetime.strptime(data_text, "%d/%m/%Y")
            except Exception:
                return datetime.min

    def filtrar_os_inicial(self):
        termo = (self.entry_busca_inicial.get() or "").strip()
        self.filtro_inicial_atual = termo
        if not termo:
            self.atualizar_lista_inicial()
            return

        resultados = buscar_ordens(self.ordens, termo)
        self.atualizar_lista_inicial(resultados)

    def limpar_busca_inicial(self):
        self.entry_busca_inicial.delete(0, tk.END)
        self.filtro_inicial_atual = ""
        self.mostrar_fechadas_flag = False
        self.atualizar_lista_inicial()

    def mostrar_os_fechadas(self):
        self.mostrar_fechadas_flag = not self.mostrar_fechadas_flag
        self.entry_busca_inicial.delete(0, tk.END)
        self.filtro_inicial_atual = ""
        self.atualizar_lista_inicial()

    def ordenar_por_os(self):
        self.ordenar_coluna_inicial("OS")

    def ordenar_por_cliente(self):
        self.ordenar_coluna_inicial("Cliente")

    def carregar_os_selecionada_inicial(self, event=None, suppress_warning=False):
        selecionado = self.tree_inicial.selection()
        if not selecionado:
            if not suppress_warning:
                messagebox.showwarning("Aviso", "Selecione uma O.S. para carregar.", parent=self.root)
            return

        item = self.tree_inicial.item(selecionado[0])
        valores = item.get("values", [])
        if not valores:
            if not suppress_warning:
                messagebox.showwarning("Aviso", "Selecione uma O.S. para carregar.", parent=self.root)
            return

        try:
            os_id = int(str(valores[0]).zfill(6))
        except Exception:
            if not suppress_warning:
                messagebox.showerror("Erro", "Não foi possível identificar a O.S.", parent=self.root)
            return

        os_item = next((o for o in self.ordens if o.get("id") == os_id), None)
        if os_item:
            self.carregar_os(os_item)
            self.abrir_tela_os()

    def on_tree_duplo_clique(self, event):
        region = self.tree_inicial.identify_region(event.x, event.y)
        if region != "heading":
            self.carregar_os_selecionada_inicial()

    def criar_nova_os(self):
        return {
            "id": len(self.ordens) + 1,
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "data_entrada": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "data_saida": "",
            "cliente": {},
            "equipamento": {},
            "acessorios": "",
            "situacao": "Aguardando autorização do orçamento",
            "tecnico": "",
            "servicos": {},
            "defeito": "",
            "obs_gerais": "",
            "obs_tecnico": "",
            "total": 0.0
        }

    def criar_cabecalho(self):
        header = tk.Frame(self.main_frame, bg="black", height=70)
        header.pack(fill="x")
        tk.Label(header, text="O.S. nº", fg="white", bg="black", font=("Arial", 16)).place(x=30, y=20)
        self.os_label = tk.Label(header, text=str(self.os_atual["id"]).zfill(6), fg="#ff0000", bg="black", font=("Arial", 28, "bold"))
        self.os_label.place(x=140, y=12)
        
        btns = tk.Frame(header, bg="black")
        btns.place(x=680, y=15)
        tk.Button(btns, text="Buscar OS", bg="#FF9800", fg="white", command=self.buscar_os).pack(side="left", padx=4)
        tk.Button(btns, text="Voltar à Lista", bg="#9E9E9E", fg="white", command=self.voltar_para_inicial).pack(side="left", padx=4)
        tk.Button(btns, text="Novo Cliente", bg="#FF9800", fg="white", command=self.cadastrar_novo_cliente).pack(side="left", padx=4)
        tk.Button(btns, text="Imprimir PDF", bg="#673AB7", fg="white", command=self.gerar_pdf).pack(side="left", padx=4)
        tk.Button(btns, text="Gravar OS", bg="#2196F3", fg="white", command=self.gravar_os).pack(side="left", padx=4)
        tk.Button(btns, text="Encerrar OS", bg="#4CAF50", fg="white", command=self.encerrar_os).pack(side="left", padx=4)
        tk.Button(btns, text="Nova OS", bg="white", command=self.nova_os).pack(side="left", padx=4)

    def criar_area_cliente(self):
        frame = tk.LabelFrame(self.main_frame, text=" Dados do Cliente ", font=("Arial", 12, "bold"), padx=10, pady=8)
        frame.pack(fill="x", padx=10, pady=8)
        self.cliente_var = tk.StringVar()
        nomes = [c.get('nome', '') for c in self.clientes]
        self.combo_cliente = ttk.Combobox(frame, textvariable=self.cliente_var, values=nomes, width=50)
        self.combo_cliente.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        tk.Button(frame, text="Carregar Dados", command=self.carregar_cliente_selecionado).grid(row=0, column=1, padx=10)
        self.info_cliente = tk.Text(frame, height=6, width=90, bg="#f9f9f9")
        self.info_cliente.grid(row=1, column=0, columnspan=3, pady=8, padx=10)

    def criar_area_equipamento(self):
        frame = tk.LabelFrame(self.main_frame, text=" Equipamento ", font=("Arial", 12, "bold"), padx=10, pady=8)
        frame.pack(fill="x", padx=10, pady=5)
        self.equipamento_entries = {}
        campos = ["Marca", "Modelo", "Número de Série"]
        for i, campo in enumerate(campos):
            tk.Label(frame, text=campo + ":").grid(row=0, column=i*2, sticky="w", padx=12, pady=8)
            entry = tk.Entry(frame, width=30)
            entry.grid(row=0, column=i*2 + 1, padx=8, pady=8)
            _vincular_maiusculas_entry(entry)
            self.equipamento_entries[campo] = entry

    def criar_area_servicos(self):
        frame = tk.LabelFrame(self.main_frame, text=" Serviços, Acessórios, Defeito e Observações ", font=("Arial", 12, "bold"))
        frame.pack(fill="both", expand=True, padx=10, pady=8)
        
        status_frame = tk.Frame(frame)
        status_frame.pack(fill="x", pady=5, padx=15)
        tk.Label(status_frame, text="Situação da OS:").pack(side="left")
        self.situacao_var = tk.StringVar(value="Aguardando autorização do orçamento")
        situacoes = self.SITUACOES_FLUXO
        ttk.Combobox(status_frame, textvariable=self.situacao_var, values=situacoes, width=35).pack(side="left", padx=10)
        
        tk.Label(status_frame, text="   Técnico Responsável:").pack(side="left")
        self.tecnico_entry = tk.Entry(status_frame, width=25)
        self.tecnico_entry.pack(side="left", padx=5)
        _vincular_maiusculas_entry(self.tecnico_entry)
        tk.Button(status_frame, text="➕", width=3, font=("Arial", 12, "bold"), command=self.cadastrar_tecnico).pack(side="left", padx=5)

        self.resumo_os_label = tk.Label(
            frame,
            text="Resumo da O.S. aparecerá aqui",
            fg="#0b5f95",
            justify="left",
            anchor="w",
            wraplength=1200,
            font=("Arial", 10)
        )
        self.resumo_os_label.pack(fill="x", padx=15, pady=(5, 0))

        conteudo = tk.Frame(frame)
        conteudo.pack(fill="both", expand=True, padx=15, pady=10)

        left = tk.Frame(conteudo)
        left.pack(side="left", fill="both", expand=True, padx=10)

        tk.Label(left, text="Acessórios:").pack(anchor="w")
        self.acessorios_text = tk.Text(left, height=3)
        self.acessorios_text.pack(fill="both", expand=True, pady=5)
        _vincular_maiusculas_texto(self.acessorios_text)

        tk.Label(left, text="Observações gerais:").pack(anchor="w")
        self.obs_gerais = tk.Text(left, height=3)
        self.obs_gerais.pack(fill="both", expand=True, pady=5)
        _vincular_maiusculas_texto(self.obs_gerais)

        tk.Label(left, text="Observações técnicas:").pack(anchor="w")
        self.obs_tecnico_text = tk.Text(left, height=3)
        self.obs_tecnico_text.pack(fill="both", expand=True, pady=5)
        _vincular_maiusculas_texto(self.obs_tecnico_text)

        right = tk.Frame(conteudo)
        right.pack(side="right", fill="both", expand=True, padx=10)

        tk.Label(right, text="Defeito / Reclamação:").pack(anchor="w")
        self.defeito_text = tk.Text(right, height=12, bg="#fafafa")
        self.defeito_text.pack(fill="both", expand=True, pady=5)
        _vincular_maiusculas_texto(self.defeito_text)

        valores_frame = tk.Frame(frame)
        valores_frame.pack(side="bottom", fill="x", padx=15, pady=10)
        self.valor_entries = {}
        itens = ["Mão-de-obra", "Peças", "Outros"]
        for i, item in enumerate(itens):
            tk.Label(valores_frame, text=item + ":").grid(row=0, column=i*2, sticky="w", padx=15)
            entry = tk.Entry(valores_frame, width=18, justify="right")
            entry.insert(0, "0.00")
            entry.bind("<KeyRelease>", self.calcular_total)
            entry.grid(row=0, column=i*2 + 1, padx=10)
            self.valor_entries[item] = entry
        
        tk.Label(valores_frame, text="TOTAL:", font=("Arial", 12, "bold")).grid(row=0, column=6, sticky="w", padx=20)
        self.total_label = tk.Label(valores_frame, text="R$ 0,00", font=("Arial", 16, "bold"), fg="red")
        self.total_label.grid(row=0, column=7, padx=10)

    def calcular_total(self, event=None):
        total = 0.0
        for entry in self.valor_entries.values():
            try:
                valor = float(entry.get().replace(',', '.'))
                total += valor
            except:
                pass
        self.total_label.config(text=f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        self.os_atual["total"] = total
        self.atualizar_resumo_os()

    def atualizar_resumo_os(self):
        cliente = self.os_atual.get("cliente", {}) or {}
        equipamento = self.os_atual.get("equipamento", {}) or {}
        tecnico = self.os_atual.get("tecnico", "") or ""
        tecnico_nome = tecnico.get("nome", "") if isinstance(tecnico, dict) else str(tecnico or "")
        detalhes_equipamento = " / ".join([part for part in [equipamento.get("Marca", ""), equipamento.get("Modelo", ""), equipamento.get("Número de Série", "")] if part]) or "Não informado"
        entrada = self.os_atual.get("data_entrada", "") or "-"
        saida = self.os_atual.get("data_saida", "") or "-"
        texto = (
            f"Cliente: {cliente.get('nome', 'Sem cliente')} | "
            f"Equipamento: {detalhes_equipamento} | "
            f"Técnico: {tecnico_nome or 'Não informado'} | "
            f"Situação: {self.os_atual.get('situacao', 'Aguardando autorização do orçamento')}"
        )
        texto2 = f"Entrada: {entrada} | Saída: {saida} | Total: R$ {_formatar_valor(self.os_atual.get('total', 0))}"
        self.resumo_os_label.config(text=f"{texto}\n{texto2}")

    def cadastrar_novo_cliente(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Novo Cliente")
        win.geometry("500x500")

        entries = {}
        campos = ["Nome", "CPF / CNPJ", "Telefone", "Email", "CEP"]

        for campo in campos:
            tk.Label(win, text=campo + ":").pack(pady=5)
            entries[campo] = tk.Entry(win, width=50)
            entries[campo].pack()
            _vincular_maiusculas_entry(entries[campo])

        def salvar_cliente():
            cep = entries["CEP"].get().strip()
            endereco = {}
            if cep and requests is not None:
                try:
                    r = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
                    endereco = r.json()
                except Exception:
                    pass

            # Separar CPF e CNPJ baseado no número de dígitos
            cpf_cnpj = _maiusc(entries["CPF / CNPJ"].get())
            cpf = ""
            cnpj = ""
            
            # Remove caracteres não numéricos para contar
            apenas_numeros = ''.join(ch for ch in cpf_cnpj if ch.isdigit())
            
            if len(apenas_numeros) == 11:
                cpf = cpf_cnpj
            elif len(apenas_numeros) == 14:
                cnpj = cpf_cnpj
            elif len(apenas_numeros) > 0:
                # Se não é nem 11 nem 14, coloca em CPF por padrão
                cpf = cpf_cnpj

            novo = {
                "id": len(self.clientes) + 1,
                "nome": _maiusc(entries["Nome"].get()),
                "cpf": cpf,
                "cnpj": cnpj,
                "telefone": _maiusc(entries["Telefone"].get()),
                "email": _maiusc(entries["Email"].get()),
                "endereco": {
                    chave: (_maiusc(valor) if isinstance(valor, str) else valor)
                    for chave, valor in (endereco or {}).items()
                },
            }

            self.clientes.append(novo)
            self.db.salvar_clientes(self.clientes)
            messagebox.showinfo("Sucesso", "Cliente cadastrado!", parent=win)
            win.destroy()
            self.combo_cliente["values"] = [c.get("nome", "") for c in self.clientes]

        tk.Button(win, text="Salvar Cliente", bg="green", fg="white", command=salvar_cliente).pack(pady=20)

    def cadastrar_tecnico(self):
        win = tk.Toplevel(self.root)
        win.title("Cadastrar Técnico")
        win.geometry("400x300")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Nome do Técnico:").pack(pady=5)
        nome = tk.Entry(win, width=40)
        nome.pack()
        _vincular_maiusculas_entry(nome)

        tk.Label(win, text="Telefone:").pack(pady=5)
        telefone = tk.Entry(win, width=40)
        telefone.pack()
        _vincular_maiusculas_entry(telefone)

        tk.Label(win, text="Especialidade:").pack(pady=5)
        especialidade = tk.Entry(win, width=40)
        especialidade.pack()
        _vincular_maiusculas_entry(especialidade)

        def salvar():
            nome_tecnico = _maiusc(nome.get().strip())
            if not nome_tecnico:
                messagebox.showwarning("Aviso", "Digite o nome do técnico.", parent=win)
                return

            tecnico = {
                "id": len(self.tecnicos) + 1,
                "nome": nome_tecnico,
                "telefone": _maiusc(telefone.get().strip()),
                "especialidade": _maiusc(especialidade.get().strip())
            }

            self.tecnicos.append(tecnico)
            self.db.salvar_tecnicos(self.tecnicos)
            self.tecnico_entry.delete(0, tk.END)
            self.tecnico_entry.insert(0, tecnico["nome"])
            win.destroy()

        tk.Button(win, text="Salvar Técnico", bg="green", fg="white", width=20, command=salvar).pack(pady=20)

    def carregar_cliente_selecionado(self):
        nome = self.cliente_var.get()
        cliente = next((c for c in self.clientes if c.get('nome') == nome), None)

        if cliente:
            self.os_atual["cliente"] = cliente
            cpf_cnpj_valor = cliente.get('cpf', '') or cliente.get('cnpj', '')
            info = (
                f"Nome: {cliente.get('nome', '')}\n"
                f"CPF/CNPJ: {cpf_cnpj_valor}\n"
                f"Telefone: {cliente.get('telefone', '')}\n"
                f"Email: {cliente.get('email', '')}\n"
            )
            end = cliente.get('endereco', {})
            if end:
                info += (
                    f"Endereço: {end.get('logradouro','')} - "
                    f"{end.get('bairro','')} - "
                    f"{end.get('localidade','')}/{end.get('uf','')}"
                )

            self.info_cliente.delete("1.0", tk.END)
            self.info_cliente.insert("1.0", info)
            self.atualizar_resumo_os()

    def buscar_os(self):
        win = tk.Toplevel(self.root)
        self.win_busca_os = win

        win.title("Buscar Ordem de Serviço")
        win.geometry("1100x700")
        win.resizable(False, False)
        win.update_idletasks()

        largura = 1100
        altura = 700
        x = (win.winfo_screenwidth() // 2) - (largura // 2)
        y = (win.winfo_screenheight() // 2) - (altura // 2)
        win.geometry(f"{largura}x{altura}+{x}+{y}")

        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Pesquisa de Ordem de Serviço", font=("Arial", 16, "bold")).pack(pady=15)

        frame_busca = tk.Frame(win)
        frame_busca.pack(pady=10)

        tk.Label(frame_busca, text="Número O.S.").grid(row=0, column=0, padx=10)
        self.entry_os = tk.Entry(frame_busca, width=18)
        self.entry_os.grid(row=1, column=0, padx=10)
        tk.Button(frame_busca, text="Buscar O.S.", width=15, command=self.filtrar_os_numero).grid(row=1, column=1, padx=10)

        tk.Label(frame_busca, text="CPF/CNPJ").grid(row=0, column=2, padx=10)
        self.entry_cpf = tk.Entry(frame_busca, width=20)
        self.entry_cpf.grid(row=1, column=2, padx=10)
        tk.Button(frame_busca, text="Buscar CPF/CNPJ", width=15, command=self.filtrar_os_cpf).grid(row=1, column=3, padx=10)
        self.entry_cpf.bind("<Return>", lambda e: self.filtrar_os_cpf())

        tk.Label(frame_busca, text="Buscar geral (cliente, CPF/CNPJ, equipamento, defeito, situação)").grid(row=0, column=4, padx=10, columnspan=3)
        self.entry_busca_geral = tk.Entry(frame_busca, width=45)
        self.entry_busca_geral.grid(row=1, column=4, padx=10, columnspan=2)
        tk.Button(frame_busca, text="Buscar Geral", width=15, command=self.filtrar_os_geral).grid(row=1, column=6, padx=10)
        self.entry_busca_geral.bind("<Return>", lambda e: self.filtrar_os_geral())

        frame_lista = tk.Frame(win)
        frame_lista.pack(pady=10)

        self.listbox_os = tk.Listbox(frame_lista, width=140, height=14, font=("Consolas", 9))
        self.listbox_os.pack()
        self.listbox_os.bind("<<ListboxSelect>>", self.atualizar_detalhes_os)

        self.texto_detalhes_os = tk.Text(frame_lista, width=140, height=8, wrap="word", font=("Arial", 9))
        self.texto_detalhes_os.pack(pady=(8, 0))
        self.texto_detalhes_os.configure(state="disabled")

        self.atualizar_lista_os()

        btns = tk.Frame(win)
        btns.pack(pady=10)
        tk.Button(btns, text="Carregar O.S. Selecionada", width=25, command=self.carregar_os_selecionada).pack(side="left", padx=8)
        tk.Button(btns, text="Limpar Filtros", width=18, command=self.limpar_filtros_os).pack(side="left", padx=8)

    def atualizar_lista_os(self):
        self.listbox_os.delete(0, tk.END)
        for os_item in sorted(self.ordens, key=lambda x: x['id'], reverse=True):
            self.listbox_os.insert(tk.END, formatar_os_para_lista(os_item))
        self.atualizar_detalhes_os()

    def limpar_filtros_os(self):
        self.entry_os.delete(0, tk.END)
        self.entry_cpf.delete(0, tk.END)
        self.entry_busca_geral.delete(0, tk.END)
        self.atualizar_lista_os()

    def filtrar_os_numero(self):
        numero = self.entry_os.get().strip()
        self.listbox_os.delete(0, tk.END)
        resultados = [os_item for os_item in self.ordens if str(os_item.get("id", "")) == numero]
        for os_item in sorted(resultados, key=lambda x: x["id"], reverse=True):
            self.listbox_os.insert(tk.END, formatar_os_para_lista(os_item))
        self.atualizar_detalhes_os()

    def filtrar_os_cpf(self):
        cpf_cnpj_busca = self.entry_cpf.get().replace(".", "").replace("-", "").replace("/", "").strip()
        if not cpf_cnpj_busca.isdigit() or (len(cpf_cnpj_busca) != 11 and len(cpf_cnpj_busca) != 14):
            messagebox.showwarning("Aviso", "CPF ou CNPJ incompleto ou incorreto.\nDigite novamente.", parent=self.root)
            return

        self.listbox_os.delete(0, tk.END)
        resultados = []
        for os_item in self.ordens:
            cliente = os_item.get("cliente", {}) or {}
            cpf = (cliente.get("cpf", "") or "").replace(".", "").replace("-", "").replace("/", "").strip()
            cnpj = (cliente.get("cnpj", "") or "").replace(".", "").replace("-", "").replace("/", "").strip()
            if cpf == cpf_cnpj_busca or cnpj == cpf_cnpj_busca:
                resultados.append(os_item)

        for os_item in sorted(resultados, key=lambda x: x["id"], reverse=True):
            self.listbox_os.insert(tk.END, formatar_os_para_lista(os_item))
        if not resultados:
            messagebox.showwarning("Aviso", "CPF/CNPJ não encontrado.", parent=self.root)
        self.atualizar_detalhes_os()

    def filtrar_os_geral(self):
        termo = self.entry_busca_geral.get().strip()
        self.listbox_os.delete(0, tk.END)
        if not termo:
            self.atualizar_lista_os()
            return

        resultados = buscar_ordens(self.ordens, termo)
        for os_item in resultados:
            self.listbox_os.insert(tk.END, formatar_os_para_lista(os_item))
        self.atualizar_detalhes_os()

    def atualizar_detalhes_os(self, event=None):
        selecionado = self.listbox_os.curselection()
        self.texto_detalhes_os.configure(state="normal")
        self.texto_detalhes_os.delete("1.0", tk.END)
        if not selecionado:
            self.texto_detalhes_os.insert("1.0", "Selecione uma O.S. para ver mais detalhes.")
            self.texto_detalhes_os.configure(state="disabled")
            return

        texto = self.listbox_os.get(selecionado[0])
        try:
            os_id = int(texto.split("|")[0].split()[-1])
        except Exception:
            self.texto_detalhes_os.insert("1.0", "Não foi possível carregar os detalhes dessa O.S.")
            self.texto_detalhes_os.configure(state="disabled")
            return

        os_item = next((item for item in self.ordens if item.get("id") == os_id), None)
        if os_item:
            self.texto_detalhes_os.insert("1.0", montar_resumo_os(os_item))
        else:
            self.texto_detalhes_os.insert("1.0", "Nenhum detalhe disponível para esta O.S.")
        self.texto_detalhes_os.configure(state="disabled")

    def carregar_os_selecionada(self):
        selecao = self.listbox_os.curselection()

        if not selecao:
            messagebox.showwarning("Aviso", "Selecione uma O.S. para carregar.", parent=self.win_busca_os)
            return

        idx = selecao[0]
        texto = self.listbox_os.get(idx)

        try:
            os_id = int(texto.split('|')[0].split()[-1])
        except Exception:
            messagebox.showerror("Erro", "Não foi possível identificar a O.S.", parent=self.win_busca_os)
            return

        os_item = next((o for o in self.ordens if o["id"] == os_id), None)

        if os_item:
            self.os_atual = os_item.copy()
            # Fecha somente a janela de pesquisa
            self.win_busca_os.destroy()
            # Carrega os dados na tela principal
            self.carregar_os(os_item)

    def carregar_os(self, os_data):
        self.os_atual = os_data.copy()

        # Número da O.S.
        self.os_label.config(text=str(self.os_atual.get("id", "")).zfill(6))

        # Cliente
        cliente = self.os_atual.get("cliente", {})
        if cliente:
            self.cliente_var.set(cliente.get("nome", ""))
            self.carregar_cliente_selecionado()

        # Equipamento
        equipamento = self.os_atual.get("equipamento", {})
        for campo, entry in self.equipamento_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, equipamento.get(campo, ""))

        # Acessórios
        self.acessorios_text.delete("1.0", tk.END)
        self.acessorios_text.insert("1.0", self.os_atual.get("acessorios", ""))

        # Defeito
        self.defeito_text.delete("1.0", tk.END)
        self.defeito_text.insert("1.0", self.os_atual.get("defeito", ""))

        # Observações gerais
        self.obs_gerais.delete("1.0", tk.END)
        self.obs_gerais.insert("1.0", self.os_atual.get("obs_gerais", ""))

        self.situacao_var.set(self.os_atual.get("situacao", "Aguardando autorização do orçamento"))

        self.obs_tecnico_text.delete("1.0", tk.END)
        self.obs_tecnico_text.insert("1.0", self.os_atual.get("obs_tecnico", ""))

        # Técnico responsável
        tecnico = self.os_atual.get("tecnico", "")
        self.tecnico_entry.delete(0, tk.END)
        if isinstance(tecnico, dict):
            self.tecnico_entry.insert(0, tecnico.get("nome", ""))
        else:
            # Compatibilidade com O.S. antigas
            self.tecnico_entry.insert(0, tecnico)

        # Carregar valores dos serviços
        servicos = self.os_atual.get("servicos", {})
        for campo, entry in self.valor_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, str(servicos.get(campo, 0.00)))

        # Atualiza o total
        self.calcular_total()

    def gravar_os(self):
        self.os_atual["equipamento"] = {k: _maiusc(v.get()) for k, v in self.equipamento_entries.items()}
        self.os_atual["acessorios"] = _maiusc(self.acessorios_text.get("1.0", tk.END).strip())
        self.os_atual["defeito"] = _maiusc(self.defeito_text.get("1.0", tk.END).strip())
        self.os_atual["obs_gerais"] = _maiusc(self.obs_gerais.get("1.0", tk.END).strip())
        self.os_atual["obs_tecnico"] = _maiusc(self.obs_tecnico_text.get("1.0", tk.END).strip())
        self.os_atual["data_entrada"] = self.os_atual.get("data_entrada", "") or datetime.now().strftime("%d/%m/%Y %H:%M")
        self.os_atual["situacao"] = self.situacao_var.get()

        tecnico_nome = _maiusc(self.tecnico_entry.get().strip())
        tecnico = next((t for t in self.tecnicos if t["nome"] == tecnico_nome), None)
        if tecnico:
            self.os_atual["tecnico"] = tecnico
        else:
            self.os_atual["tecnico"] = {"nome": tecnico_nome}
            
        self.os_atual["servicos"] = {k: float(v.get() or 0) for k, v in self.valor_entries.items()}
        self.os_atual["total"] = sum(self.os_atual["servicos"].values())
        self.os_atual["data"] = self.os_atual.get("data", datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        for i, item in enumerate(self.ordens):
            if item["id"] == self.os_atual["id"]:
                self.ordens[i] = self.os_atual
                break
        else:
            self.ordens.append(self.os_atual)
        
        if self.db.salvar_ordens(self.ordens):
            self.atualizar_resumo_os()
            # Mantém a lista da tela inicial sincronizada com a O.S. recém-gravada,
            # respeitando eventual busca em andamento.
            self.atualizar_lista_inicial(buscar_ordens(self.ordens, self.filtro_inicial_atual))
            messagebox.showinfo("Sucesso", f"OS {self.os_atual['id']} salva!")

    def encerrar_os(self):
        if messagebox.askyesno("Encerrar OS", "Deseja encerrar esta Ordem de Serviço?"):
            self.situacao_var.set("Encerrada")
            self.os_atual["data_saida"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            self.gravar_os()
            messagebox.showinfo("Concluído", f"OS {self.os_atual['id']} encerrada em {self.os_atual['data_saida']}!")

    def nova_os(self):
        if messagebox.askyesno("Nova OS", "Criar nova Ordem de Serviço?"):
            self.os_atual = self.criar_nova_os()
            self.os_label.config(text=str(self.os_atual["id"]).zfill(6))
            for entry in self.equipamento_entries.values():
                entry.delete(0, tk.END)
            for entry in self.valor_entries.values():
                entry.delete(0, tk.END)
                entry.insert(0, "0.00")
            self.acessorios_text.delete("1.0", tk.END)
            self.defeito_text.delete("1.0", tk.END)
            self.obs_gerais.delete("1.0", tk.END)
            self.obs_tecnico_text.delete("1.0", tk.END)
            self.info_cliente.delete("1.0", tk.END)
            self.cliente_var.set("")
            self.situacao_var.set("Aguardando autorização do orçamento")
            self.tecnico_entry.delete(0, tk.END)
            self.calcular_total()
            self.atualizar_resumo_os()

    def gerar_pdf(self):
        if not REPORTLAB_DISPONIVEL:
            messagebox.showwarning("Aviso", "A biblioteca reportlab não está disponível. Instale-a com: pip install reportlab")
            return

        try:
            from reportlab.platypus import Table, TableStyle, Spacer, Paragraph
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            
            pasta_documentos = obter_pasta_documentos()
            os.makedirs(pasta_documentos, exist_ok=True)
            filename = os.path.join(pasta_documentos, f"OS_{self.os_atual['id']:06d}.pdf")
            doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=1*cm, leftMargin=1*cm, topMargin=0.8*cm, bottomMargin=0.8*cm)
            styles = getSampleStyleSheet()
            story = []
            
            # ===== CABEÇALHO =====
            header_data = [
                ['NAND ASSISTÊNCIA', f"Orçamento da Ordem de Serviço {self.os_atual['id']:06d}"],
            ]
            header_table = Table(header_data, colWidths=[7*cm, 11*cm])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (0, 0), 15),
                ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (1, 0), (1, 0), 12),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('LEFTPADDING', (0, 0), (-1, 0), 10),
                ('RIGHTPADDING', (0, 0), (-1, 0), 10),
            ]))
            story.append(header_table)
            story.append(Spacer(1, 0.25*cm))
            
            # ===== INFORMAÇÕES DO CLIENTE =====
            cliente = self.os_atual.get("cliente", {}) or {}
            equipamento = self.os_atual.get("equipamento", {}) or {}
            
            # Extrair dados de endereço que vem da API ViaCEP
            endereco_dict = cliente.get('endereco', {}) or {}
            
            # Se endereco é um dicionário com dados da ViaCEP
            if isinstance(endereco_dict, dict) and endereco_dict.get('logradouro'):
                endereco_completo = f"{endereco_dict.get('logradouro', '-')} {endereco_dict.get('numero', '-')}"
                cep = endereco_dict.get('cep', '-')
                bairro = endereco_dict.get('bairro', '-')
                cidade = endereco_dict.get('localidade', '-')
            else:
                endereco_completo = '-'
                cep = '-'
                bairro = '-'
                cidade = '-'
            
            cpf_cnpj_val = cliente.get('cpf') or cliente.get('cnpj') or '-'
            info_cliente_data = [
                ['Cliente', cliente.get('nome', '-'), 'Contato', cliente.get('telefone', '-')],
                ['Endereço', endereco_completo, 'CEP', cep],
                ['Bairro', bairro, 'Cidade', cidade],
                ['CPF/CNPJ', cpf_cnpj_val, 'Email', cliente.get('email', '-')],
            ]
            
            info_table = Table(info_cliente_data, colWidths=[2.3*cm, 6.2*cm, 2.3*cm, 6.2*cm])
            info_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
                ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ECF0F1')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.2*cm))
            
            # ===== INFORMAÇÕES DO EQUIPAMENTO =====
            marca = equipamento.get('Marca', '-')
            modelo = equipamento.get('Modelo', '-')
            serie = equipamento.get('Número de Série', '-')
            
            equip_data = [
                ['Marca', marca, 'Modelo', modelo],
                ['Nº Série', serie, 'Acessórios', self.os_atual.get('acessorios', '-')],
            ]
            
            equip_table = Table(equip_data, colWidths=[2.3*cm, 6.2*cm, 2.3*cm, 6.2*cm])
            equip_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8.5),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
                ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#ECF0F1')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ]))
            story.append(equip_table)
            story.append(Spacer(1, 0.25*cm))
            
            # ===== DEFEITO/RECLAMAÇÃO =====
            defeito_titulo = Paragraph("<b>DEFEITO/RECLAMAÇÃO</b>", styles['Normal'])
            story.append(defeito_titulo)
            
            defeito_box_data = [
                [self.os_atual.get('defeito', '-') or '-'],
            ]
            defeito_box = Table(defeito_box_data, colWidths=[16.5*cm])
            defeito_box.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8.5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(defeito_box)
            story.append(Spacer(1, 0.25*cm))
            
            # ===== VALORES DO ORÇAMENTO =====
            valores_titulo = Paragraph("<b>VALORES DO ORÇAMENTO</b>", styles['Normal'])
            story.append(valores_titulo)
            
            servicos = self.os_atual.get('servicos', {}) or {}
            valores_data = [['Descrição', 'Quantidade', 'Valor Unitário', 'Total']]
            
            for descricao, valor in servicos.items():
                try:
                    valor_float = float(valor) if isinstance(valor, (int, float, str)) else 0
                    if valor_float > 0:
                        valor_formatado = _formatar_valor(valor_float)
                        valores_data.append([descricao, '1', valor_formatado, valor_formatado])
                except:
                    pass
            
            if len(valores_data) == 1:
                valores_data.append(['(Sem itens)', '', '', ''])
            
            valores_table = Table(valores_data, colWidths=[6.5*cm, 2.5*cm, 3.5*cm, 3.5*cm])
            valores_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('FONTSIZE', (0, 1), (-1, -1), 8.5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9F9')]),
            ]))
            story.append(valores_table)
            story.append(Spacer(1, 0.2*cm))
            
            # ===== TOTAIS =====
            total_valor = _formatar_valor(self.os_atual.get('total', 0))
            
            totais_data = [
                ['Mão de obra/Serviço', 'R$ 0,00'],
                ['Peças e Materiais', f'R$ {total_valor}'],
                ['Outros', 'R$ 0,00'],
                ['TOTAL', f'R$ {total_valor}'],
            ]
            
            totais_table = Table(totais_data, colWidths=[13*cm, 4*cm])
            totais_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
                ('FONTSIZE', (0, 0), (0, -2), 8.5),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 0), (-1, -2), [colors.white, colors.HexColor('#F8F9F9')]),
            ]))
            story.append(totais_table)
            story.append(Spacer(1, 0.6*cm))
            
            # ===== ASSINATURAS =====
            assinatura_data = [
                ['_' * 28, '', '_' * 28],
                ['CLIENTE', '', 'NAND ASSISTÊNCIA'],
            ]
            assinatura_table = Table(assinatura_data, colWidths=[5*cm, 6.5*cm, 5*cm])
            assinatura_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, 1), 9),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, 0), 'BOTTOM'),
                ('TOPPADDING', (0, 0), (-1, 0), 25),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 3),
            ]))
            story.append(assinatura_table)
            
            # ===== TERMO DE COMPROVANTE DE ENTRADA =====
            story.append(Spacer(1, 0.4*cm))
            termo_titulo = Paragraph("<b>COMPROVANTE DE ENTRADA DO EQUIPAMENTO</b>", styles['Normal'])
            story.append(termo_titulo)
            story.append(Spacer(1, 0.2*cm))
            
            termo_texto = """
<b>PREZADO(A) CLIENTE,</b><br/><br/>
Guarde este comprovante de entrada, pois ele é necessário para a retirada do equipamento. 
Sua apresentação garante a segurança na identificação. Na ausência, a retirada poderá ocorrer 
mediante validação da identidade do responsável, conforme procedimentos internos.<br/><br/>

<b>Responsabilidade sobre dados:</b> O cliente declara estar ciente de que, durante a execução dos serviços, 
poderá ocorrer perda parcial ou total de dados. É de sua responsabilidade realizar backup prévio. 
A empresa não se responsabiliza pela perda, recuperação ou integridade de dados, salvo em caso de 
dolo ou culpa grave, conforme legislação vigente.<br/><br/>

<b>Prazo para retirada:</b> Conforme art. 592 do Código Civil e orientações do Procon, equipamentos não 
retirados em até 90 (noventa) dias poderão ser considerados abandonados, podendo ser destinados à 
compensação de custos com armazenamento e serviços, mediante tentativa prévia de contato.<br/><br/>

<b>Garantia:</b> Não cobre danos por mau uso, quedas, instalações inadequadas, variações elétricas 
ou intervenções de terceiros não autorizados.
            """
            
            termo_paragraph = Paragraph(termo_texto, styles['Normal'])
            termo_box_data = [[termo_paragraph]]
            termo_box = Table(termo_box_data, colWidths=[16.5*cm])
            termo_box.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),
            ]))
            story.append(termo_box)
            
            doc.build(story)
            messagebox.showinfo("PDF Gerado", f"Arquivo salvo como: {filename}")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível gerar o PDF: {e}")


    def sair(self):
        if self.main_frame.winfo_ismapped():
            self.voltar_para_inicial()
            return

        if messagebox.askokcancel("Sair", "Deseja sair?"):
            self.root.destroy()

if __name__ == "__main__":
    OrdemServicoApp()