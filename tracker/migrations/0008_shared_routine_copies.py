from django.db import migrations


class Migration(migrations.Migration):

	dependencies = [
		("tracker", "0007_entrenamiento_es_plantilla_entrenamiento_plantilla_and_more"),
	]

	operations = [
		migrations.RemoveField(
			model_name="entrenamiento",
			name="plantilla",
		),
		migrations.RemoveField(
			model_name="entrenamiento",
			name="es_plantilla",
		),
	]
