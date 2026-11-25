from django.db import migrations


OBSOLETE_TABLES = (
	"tracker_perfilusuario",
	"tracker_datoarchivado",
	"django_admin_log",
)


def remove_unused_schema(apps, schema_editor):
	connection = schema_editor.connection
	quote_name = schema_editor.quote_name
	tables = set(connection.introspection.table_names())

	for table_name in OBSOLETE_TABLES:
		if table_name in tables:
			schema_editor.execute(f"DROP TABLE {quote_name(table_name)}")

	assignment_model = apps.get_model("tracker", "UsuarioEntrenamiento")
	table_name = assignment_model._meta.db_table
	if table_name not in tables:
		return

	with connection.cursor() as cursor:
		columns = {
			column.name
			for column in connection.introspection.get_table_description(
				cursor, table_name
			)
		}
	if "fecha_asignacion" in columns:
		schema_editor.execute(
			f"ALTER TABLE {quote_name(table_name)} "
			f"DROP COLUMN {quote_name('fecha_asignacion')}"
		)


class Migration(migrations.Migration):
	atomic = False

	dependencies = [("tracker", "0015_ejercicio_mide_tiempo_and_more")]

	operations = [migrations.RunPython(remove_unused_schema, migrations.RunPython.noop)]