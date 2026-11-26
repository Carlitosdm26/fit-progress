from django.db import migrations, models


def mark_existing_series_complete(apps, schema_editor):
	Serie = apps.get_model("tracker", "Serie")
	Serie.objects.using(schema_editor.connection.alias).update(completada=True)


class Migration(migrations.Migration):
	atomic = False

	dependencies = [("tracker", "0016_remove_unused_schema")]

	operations = [
		migrations.AddField(
			model_name="serie",
			name="completada",
			field=models.BooleanField(default=False),
		),
		migrations.RunPython(
			mark_existing_series_complete,
			migrations.RunPython.noop,
		),
	]
