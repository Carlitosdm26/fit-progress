from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0013_add_exercise_visual_guides"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ejercicio",
            name="guia_imagen",
        ),
        migrations.RemoveField(
            model_name="ejercicio",
            name="video_url",
        ),
    ]
