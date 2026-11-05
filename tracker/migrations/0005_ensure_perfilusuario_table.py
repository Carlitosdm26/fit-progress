from django.db import migrations


def ensure_perfilusuario_table(apps, schema_editor):
	PerfilUsuario = apps.get_model("tracker", "PerfilUsuario")
	table_name = PerfilUsuario._meta.db_table
	if table_name not in schema_editor.connection.introspection.table_names():
		schema_editor.create_model(PerfilUsuario)


class Migration(migrations.Migration):
	dependencies = [("tracker", "0004_update_existing_schema")]

	operations = [
		migrations.RunPython(ensure_perfilusuario_table, migrations.RunPython.noop)
	]