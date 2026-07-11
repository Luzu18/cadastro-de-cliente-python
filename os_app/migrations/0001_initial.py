from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Cliente",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(blank=True, default="", max_length=255)),
                ("cpf", models.CharField(blank=True, default="", max_length=32)),
                ("telefone", models.CharField(blank=True, default="", max_length=32)),
                ("email", models.CharField(blank=True, default="", max_length=255)),
                ("endereco", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="Tecnico",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(blank=True, default="", max_length=255)),
                ("telefone", models.CharField(blank=True, default="", max_length=32)),
                ("especialidade", models.CharField(blank=True, default="", max_length=255)),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="OrdemServico",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.CharField(blank=True, default="", max_length=32)),
                ("data_entrada", models.CharField(blank=True, default="", max_length=32)),
                ("data_saida", models.CharField(blank=True, default="", max_length=32)),
                ("cliente_dados", models.JSONField(blank=True, default=dict)),
                ("equipamento", models.JSONField(blank=True, default=dict)),
                ("acessorios", models.TextField(blank=True, default="")),
                ("situacao", models.CharField(blank=True, default="", max_length=64)),
                ("tecnico_dados", models.JSONField(blank=True, default=dict)),
                ("servicos", models.JSONField(blank=True, default=dict)),
                ("defeito", models.TextField(blank=True, default="")),
                ("obs_gerais", models.TextField(blank=True, default="")),
                ("obs_tecnico", models.TextField(blank=True, default="")),
                ("total", models.FloatField(default=0.0)),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
