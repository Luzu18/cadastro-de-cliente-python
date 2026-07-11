"""
Configuração mínima do Django, usada apenas para ligar o ORM (models +
migrations) ao banco SQLite do cliente_manager.py. Não há servidor web
aqui — é só a base necessária para o Django gerenciar o banco de dados.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Chave exigida pelo Django para inicializar. Como o app roda 100% local
# (desktop, sem servidor exposto), não há necessidade de tratá-la como
# segredo sensível — mas se quiser, pode trocar por qualquer texto seu.
SECRET_KEY = "chave-uso-local-cliente-manager-desktop"

DEBUG = False

INSTALLED_APPS = [
    "os_app",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "os_database.db"),
    }
}

USE_TZ = False
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
