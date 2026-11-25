import django.db.models.deletion
from django.db import migrations, models


def copy_shared_routines(apps, schema_editor):
	Entrenamiento = apps.get_model("tracker", "Entrenamiento")
	EntrenamientoEjercicio = apps.get_model("tracker", "EntrenamientoEjercicio")
	UsuarioEntrenamiento = apps.get_model("tracker", "UsuarioEntrenamiento")
	UsuarioEntrenamientoEjercicio = apps.get_model(
		"tracker", "UsuarioEntrenamientoEjercicio"
	)
	database = schema_editor.connection.alias

	for routine_id in Entrenamiento.objects.using(database).values_list("pk", flat=True):
		routine = Entrenamiento.objects.using(database).get(pk=routine_id)
		entries = list(
			EntrenamientoEjercicio.objects.using(database)
			.filter(entrenamiento_id=routine_id)
			.order_by("orden", "pk")
		)
		assignments = list(
			UsuarioEntrenamiento.objects.using(database)
			.filter(entrenamiento_id=routine_id)
			.order_by("pk")
		)

		for assignment in assignments:
			copy = Entrenamiento.objects.using(database).create(
				nombre=routine.nombre,
				descripcion=routine.descripcion,
			)
			entries_by_id = {}
			entries_by_exercise = {}
			for entry in entries:
				copy_entry = EntrenamientoEjercicio.objects.using(database).create(
					entrenamiento_id=copy.pk,
					ejercicio_id=entry.ejercicio_id,
					orden=entry.orden,
				)
				entries_by_id[entry.pk] = copy_entry
				entries_by_exercise[entry.ejercicio_id] = copy_entry

			selections = UsuarioEntrenamientoEjercicio.objects.using(database).filter(
				usuario_entrenamiento_id=assignment.pk
			)
			for selection in selections:
				copy_entry = entries_by_id.get(selection.entrenamiento_ejercicio_id)
				if copy_entry is None:
					original_entry = EntrenamientoEjercicio.objects.using(database).get(
						pk=selection.entrenamiento_ejercicio_id
					)
					copy_entry = entries_by_exercise.get(original_entry.ejercicio_id)
					if copy_entry is None:
						next_order = max(
							(entry.orden for entry in entries_by_exercise.values()),
							default=0,
						) + 1
						copy_entry = EntrenamientoEjercicio.objects.using(database).create(
							entrenamiento_id=copy.pk,
							ejercicio_id=original_entry.ejercicio_id,
							orden=next_order,
						)
						entries_by_exercise[original_entry.ejercicio_id] = copy_entry
				selection.entrenamiento_ejercicio_id = copy_entry.pk
				selection.save(using=database, update_fields=["entrenamiento_ejercicio"])

			assignment.entrenamiento_id = copy.pk
			assignment.save(using=database, update_fields=["entrenamiento"])


class Migration(migrations.Migration):
	replaces = [
		(
			"tracker",
			"0007_entrenamiento_es_plantilla_entrenamiento_plantilla_and_more",
		),
		("tracker", "0008_shared_routine_copies"),
	]

	dependencies = [("tracker", "0004_squashed_0006")]

	operations = [
		migrations.AddField(
			model_name="usuarioentrenamientoejercicio",
			name="activo",
			field=models.BooleanField(default=True),
		),
		migrations.RunPython(copy_shared_routines, migrations.RunPython.noop),
	]