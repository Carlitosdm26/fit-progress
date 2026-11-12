from django.db import migrations, models
from django.db.models import Min


def backfill_session_exercise_order(apps, schema_editor):
	Serie = apps.get_model("tracker", "Serie")
	database = schema_editor.connection.alias
	ordenes = {}
	sesion_actual = None
	orden_actual = 0
	for grupo in (
		Serie.objects.using(database)
		.values("sesion_entrenamiento_id", "usuario_entrenamiento_ejercicio_id")
		.annotate(primera_serie=Min("pk"))
		.order_by("sesion_entrenamiento_id", "primera_serie")
		.iterator(chunk_size=500)
	):
		if grupo["sesion_entrenamiento_id"] != sesion_actual:
			sesion_actual = grupo["sesion_entrenamiento_id"]
			orden_actual = 1
		else:
			orden_actual += 1
		ordenes[
			(
				grupo["sesion_entrenamiento_id"],
				grupo["usuario_entrenamiento_ejercicio_id"],
			)
		] = orden_actual

	batch = []
	for serie in Serie.objects.using(database).iterator(chunk_size=500):
		serie.orden_ejercicio = ordenes[
			(
				serie.sesion_entrenamiento_id,
				serie.usuario_entrenamiento_ejercicio_id,
			)
		]
		batch.append(serie)
		if len(batch) == 500:
			Serie.objects.using(database).bulk_update(
				batch, ["orden_ejercicio"], batch_size=500
			)
			batch.clear()
	if batch:
		Serie.objects.using(database).bulk_update(
			batch, ["orden_ejercicio"], batch_size=500
		)


class Migration(migrations.Migration):
	dependencies = [("tracker", "0013_add_exercise_visual_guides")]

	operations = [
		migrations.AddField(
			model_name="serie",
			name="orden_ejercicio",
			field=models.PositiveIntegerField(default=1),
		),
		migrations.AlterModelOptions(
			name="serie",
			options={
				"ordering": [
					"orden_ejercicio",
					"usuario_entrenamiento_ejercicio_id",
					"numero_serie",
				]
			},
		),
		migrations.RunPython(
			backfill_session_exercise_order,
			migrations.RunPython.noop,
		),
	]
