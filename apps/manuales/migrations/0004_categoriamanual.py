from django.db import migrations, models


def copiar_categorias(apps, schema_editor):
    Manual = apps.get_model("manuales", "Manual")
    CategoriaManual = apps.get_model("manuales", "CategoriaManual")
    vistas = set()
    for nombre in Manual.objects.values_list("categoria", flat=True).distinct():
        limpio = " ".join((nombre or "").split())
        if limpio and limpio.lower() not in vistas:
            vistas.add(limpio.lower())
            CategoriaManual.objects.get_or_create(nombre=limpio)


class Migration(migrations.Migration):

    dependencies = [
        ("manuales", "0003_manual_solicitud_eliminacion"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoriaManual",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80, unique=True)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Categoría de manual",
                "verbose_name_plural": "Categorías de manuales",
                "ordering": ["nombre"],
            },
        ),
        migrations.RunPython(copiar_categorias, migrations.RunPython.noop),
    ]