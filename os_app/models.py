"""
Models Django que representam as três entidades do cliente_manager.py:
Cliente, Técnico e Ordem de Serviço.

Os campos "endereco", "equipamento", "servicos" e "tecnico_dados" usam
JSONField porque no programa original eles já eram dicionários livres
(ex.: endereço vindo da API do ViaCEP, serviços com valores variáveis).
Guardar como JSON evita ter que criar uma tabela separada para cada um
desses sub-dados, mantendo o CRUD simples.

Cada model tem um to_dict() que devolve exatamente o mesmo formato de
dicionário que o cliente_manager.py já espera — assim o restante do
programa (telas, busca, geração de PDF etc.) não precisa mudar nada.
"""

from django.db import models


class Cliente(models.Model):
    nome = models.CharField(max_length=255, blank=True, default="")
    cpf = models.CharField(max_length=32, blank=True, default="")
    cnpj = models.CharField(max_length=32, blank=True, default="")
    telefone = models.CharField(max_length=32, blank=True, default="")
    email = models.CharField(max_length=255, blank=True, default="")
    endereco = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nome or f"Cliente {self.id}"

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "cpf": self.cpf,
            "cnpj": self.cnpj,
            "telefone": self.telefone,
            "email": self.email,
            "endereco": self.endereco or {},
        }


class Tecnico(models.Model):
    nome = models.CharField(max_length=255, blank=True, default="")
    telefone = models.CharField(max_length=32, blank=True, default="")
    especialidade = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nome or f"Técnico {self.id}"

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "telefone": self.telefone,
            "especialidade": self.especialidade,
        }


class OrdemServico(models.Model):
    data = models.CharField(max_length=32, blank=True, default="")
    data_entrada = models.CharField(max_length=32, blank=True, default="")
    data_saida = models.CharField(max_length=32, blank=True, default="")
    cliente_dados = models.JSONField(blank=True, default=dict)
    equipamento = models.JSONField(blank=True, default=dict)
    acessorios = models.TextField(blank=True, default="")
    situacao = models.CharField(max_length=64, blank=True, default="")
    tecnico_dados = models.JSONField(blank=True, default=dict)
    servicos = models.JSONField(blank=True, default=dict)
    defeito = models.TextField(blank=True, default="")
    obs_gerais = models.TextField(blank=True, default="")
    obs_tecnico = models.TextField(blank=True, default="")
    total = models.FloatField(default=0.0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"OS {self.id}"

    def to_dict(self):
        return {
            "id": self.id,
            "data": self.data,
            "data_entrada": self.data_entrada,
            "data_saida": self.data_saida,
            "cliente": self.cliente_dados or {},
            "equipamento": self.equipamento or {},
            "acessorios": self.acessorios,
            "situacao": self.situacao,
            "tecnico": self.tecnico_dados if self.tecnico_dados else "",
            "servicos": self.servicos or {},
            "defeito": self.defeito,
            "obs_gerais": self.obs_gerais,
            "obs_tecnico": self.obs_tecnico,
            "total": self.total,
        }
