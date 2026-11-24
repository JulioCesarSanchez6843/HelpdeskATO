import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("manuales", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="manual",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente de aprobación"),
                    ("APROBADO", "Aprobado"),
                ],
                default="APROBADO",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="manual",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente de aprobación"),
                    ("APROBADO", "Aprobado"),
                ],
                default="PENDIENTE",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="manual",
            name="aprobado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="manual",
            name="aprobado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]