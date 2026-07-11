"""
Camada de persistência do cliente_manager.py, agora usando o Django ORM.

O cliente_manager.py continua chamando `Database()` e os mesmos métodos
de sempre (carregar_clientes, salvar_clientes, carregar_tecnicos,
salvar_tecnicos, carregar_ordens, salvar_ordens) — só que por baixo dos
panos, cada operação agora vira uma consulta/gravação CRUD real feita
pelo ORM do Django nos models de os_app/models.py, usando as migrations
do Django para criar e manter as tabelas em os_database.db.

Este módulo inicializa o Django em modo "standalone" (sem servidor web,
sem urls.py) — é só o ORM sendo usado dentro de um app desktop comum.
"""

import os
import sys
import json as _json
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Quando empacotado com PyInstaller, os arquivos ficam em sys._MEIPASS.
# Garantir que o diretório correto esteja no sys.path e que o módulo
# `settings` seja importável — se necessário, carregamos o arquivo
# `settings.py` explicitamente para evitar "No module named 'settings'".
bundle_dir = getattr(sys, '_MEIPASS', BASE_DIR)
if bundle_dir not in sys.path:
    sys.path.insert(0, bundle_dir)

try:
    import settings  # noqa: E402,F401 - prefer import normal quando possível
except Exception:
    # Tenta carregar manualmente do arquivo settings.py que está ao lado do bundle
    settings_path = os.path.join(bundle_dir, 'settings.py')
    if os.path.exists(settings_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location('settings', settings_path)
        settings = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(settings)  # type: ignore
        sys.modules['settings'] = settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django  # noqa: E402
django.setup()

from django.core.management import call_command  # noqa: E402
from os_app.models import Cliente, Tecnico, OrdemServico  # noqa: E402

CAMINHO_BANCO = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), "os_database.db")

_inicializado = False


def _garantir_banco_pronto():
    """Aplica as migrations do Django (cria/atualiza as tabelas do banco)
    e, se existirem tabelas da versão anterior (sqlite3 puro), importa os
    dados delas uma única vez. Só roda esse trabalho uma vez por execução."""
    global _inicializado
    if _inicializado:
        return
    call_command("migrate", verbosity=0)
    _migrar_dados_legado()
    _inicializado = True


def _migrar_dados_legado():
    """Se o banco ainda tiver as tabelas 'clientes', 'tecnicos' e
    'ordens_servico' no formato antigo (da versão com sqlite3 puro, sem
    Django), importa os dados delas para os models do Django e depois
    renomeia essas tabelas antigas com o prefixo '_legado_' — assim elas
    viram só um backup e não são importadas de novo nas próximas vezes."""
    if not os.path.exists(CAMINHO_BANCO):
        return

    conn = sqlite3.connect(CAMINHO_BANCO)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabelas = {row["name"] for row in cur.fetchall()}

    if "clientes" in tabelas:
        cur.execute("SELECT * FROM clientes")
        for row in cur.fetchall():
            Cliente.objects.update_or_create(
                id=row["id"],
                defaults={
                    "nome": row["nome"] or "",
                    "cpf": row["cpf"] or "",
                    "cnpj": "",
                    "telefone": row["telefone"] or "",
                    "email": row["email"] or "",
                    "endereco": _json.loads(row["endereco_json"]) if row["endereco_json"] else {},
                },
            )
        cur.execute("ALTER TABLE clientes RENAME TO _legado_clientes")

    if "tecnicos" in tabelas:
        cur.execute("SELECT * FROM tecnicos")
        for row in cur.fetchall():
            Tecnico.objects.update_or_create(
                id=row["id"],
                defaults={
                    "nome": row["nome"] or "",
                    "telefone": row["telefone"] or "",
                    "especialidade": row["especialidade"] or "",
                },
            )
        cur.execute("ALTER TABLE tecnicos RENAME TO _legado_tecnicos")

    if "ordens_servico" in tabelas:
        cur.execute("SELECT * FROM ordens_servico")
        for row in cur.fetchall():
            OrdemServico.objects.update_or_create(
                id=row["id"],
                defaults={
                    "data": row["data"] or "",
                    "data_entrada": row["data_entrada"] or "",
                    "data_saida": row["data_saida"] or "",
                    "cliente_dados": _json.loads(row["cliente_json"]) if row["cliente_json"] else {},
                    "equipamento": _json.loads(row["equipamento_json"]) if row["equipamento_json"] else {},
                    "acessorios": row["acessorios"] or "",
                    "situacao": row["situacao"] or "",
                    "tecnico_dados": _json.loads(row["tecnico_json"]) if row["tecnico_json"] else "",
                    "servicos": _json.loads(row["servicos_json"]) if row["servicos_json"] else {},
                    "defeito": row["defeito"] or "",
                    "obs_gerais": row["obs_gerais"] or "",
                    "obs_tecnico": row["obs_tecnico"] or "",
                    "total": row["total"] if row["total"] is not None else 0.0,
                },
            )
        cur.execute("ALTER TABLE ordens_servico RENAME TO _legado_ordens_servico")

    conn.commit()
    conn.close()


class Database:
    """Mesma interface de antes — quem chama (cliente_manager.py) não
    precisa saber que agora é o Django ORM cuidando do CRUD por dentro."""

    def __init__(self, *_args, **_kwargs):
        _garantir_banco_pronto()

    # ---------- Clientes ----------
    def carregar_clientes(self):
        return [c.to_dict() for c in Cliente.objects.all()]

    def salvar_clientes(self, clientes):
        for c in clientes:
            Cliente.objects.update_or_create(
                id=c.get("id"),
                defaults={
                    "nome": c.get("nome", ""),
                    "cpf": c.get("cpf", ""),
                    "cnpj": c.get("cnpj", ""),
                    "telefone": c.get("telefone", ""),
                    "email": c.get("email", ""),
                    "endereco": c.get("endereco", {}) or {},
                },
            )
        return True

    # ---------- Técnicos ----------
    def carregar_tecnicos(self):
        return [t.to_dict() for t in Tecnico.objects.all()]

    def salvar_tecnicos(self, tecnicos):
        for t in tecnicos:
            Tecnico.objects.update_or_create(
                id=t.get("id"),
                defaults={
                    "nome": t.get("nome", ""),
                    "telefone": t.get("telefone", ""),
                    "especialidade": t.get("especialidade", ""),
                },
            )
        return True

    # ---------- Ordens de Serviço ----------
    def carregar_ordens(self):
        return [o.to_dict() for o in OrdemServico.objects.all()]

    def salvar_ordens(self, ordens):
        for o in ordens:
            OrdemServico.objects.update_or_create(
                id=o.get("id"),
                defaults={
                    "data": o.get("data", ""),
                    "data_entrada": o.get("data_entrada", ""),
                    "data_saida": o.get("data_saida", ""),
                    "cliente_dados": o.get("cliente", {}) or {},
                    "equipamento": o.get("equipamento", {}) or {},
                    "acessorios": o.get("acessorios", ""),
                    "situacao": o.get("situacao", ""),
                    "tecnico_dados": o.get("tecnico", "") or "",
                    "servicos": o.get("servicos", {}) or {},
                    "defeito": o.get("defeito", ""),
                    "obs_gerais": o.get("obs_gerais", ""),
                    "obs_tecnico": o.get("obs_tecnico", ""),
                    "total": float(o.get("total", 0) or 0),
                },
            )
        return True

    def fechar(self):
        # O Django gerencia as conexões com o banco sozinho, então não há
        # nada para fechar manualmente aqui — mantido só por compatibilidade.
        pass
