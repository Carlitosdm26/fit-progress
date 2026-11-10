from django.db import migrations


def flatten_routine_copy_links(apps, schema_editor):
	Entrenamiento = apps.get_model("tracker", "Entrenamiento")
	parents = dict(
		Entrenamiento.objects.values_list("pk", "plantilla_id")
	)
	for routine_id, parent_id in parents.items():
		root_id = parent_id
		seen = {routine_id}
		while root_id is not None and root_id in parents and root_id not in seen:
			seen.add(root_id)
			next_parent_id = parents[root_id]
			if next_parent_id is None:
				break
			root_id = next_parent_id
		if parent_id is not None and root_id != parent_id:
			Entrenamiento.objects.filter(pk=routine_id).update(plantilla_id=root_id)
			parents[routine_id] = root_id


class Migration(migrations.Migration):

	dependencies = [
		("tracker", "0007_entrenamiento_es_plantilla_entrenamiento_plantilla_and_more"),
	]

	operations = [
		migrations.RunPython(flatten_routine_copy_links, migrations.RunPython.noop),
		migrations.RenameField(
			model_name="entrenamiento",
			old_name="plantilla",
			new_name="rutina_origen",
		),
		migrations.RemoveField(
			model_name="entrenamiento",
			name="es_plantilla",
		),
	]
