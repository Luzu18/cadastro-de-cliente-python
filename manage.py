#!/usr/bin/env python
"""Utilitário de linha de comando do Django para este projeto."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Verifique se ele está "
            "instalado (pip install django) e se você está no ambiente "
            "Python correto."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
