from django.db import migrations, models


ARCHIVED_FIELDS = {
	"entrenamiento": ("notas",),
	"entrenamientoejercicio": ("notas",),
	"usuarioentrenamientoejercicio": ("notas",),
	"serie": ("notas",),
}


def _columns(connection, table_name):
	with connection.cursor() as cursor:
		return {
			column.name
			for column in connection.introspection.get_table_description(
				cursor, table_name
			)
		}


def _remove_column(schema_editor, model, field_name):
	connection = schema_editor.connection
	table_name = model._meta.db_table
	columns = _columns(connection, table_name)
	if field_name not in columns:
		return

	quote_name = schema_editor.quote_name
	schema_editor.execute(
		f"ALTER TABLE {quote_name(table_name)} DROP COLUMN {quote_name(field_name)}"
	)


def update_existing_schema(apps, schema_editor):
	connection = schema_editor.connection
	alias = connection.alias
	content_type_model = apps.get_model("contenttypes", "ContentType")
	old_content_type = content_type_model.objects.using(alias).filter(
		app_label="auth", model="user"
	).first()
	if old_content_type is not None:
		conflicting_content_type = content_type_model.objects.using(alias).filter(
			app_label="tracker", model="usuario"
		).exclude(pk=old_content_type.pk).exists()
		if conflicting_content_type:
			raise RuntimeError(
				"Ya existe el tipo de contenido tracker.usuario. "
				"Revisa permisos antes de continuar con la migración."
			)
		permission_model = apps.get_model("auth", "Permission")
		existing_codenames = set(
			permission_model.objects.using(alias)
			.filter(content_type_id=old_content_type.pk)
			.values_list("codename", flat=True)
		)
		codename_map = {
			"add_user": "add_usuario",
			"change_user": "change_usuario",
			"delete_user": "delete_usuario",
			"view_user": "view_usuario",
		}
		if any(
			old_codename in existing_codenames
			and new_codename in existing_codenames
			for old_codename, new_codename in codename_map.items()
		):
			raise RuntimeError(
				"Hay permisos duplicados para el usuario. "
				"Revisa los permisos antes de continuar con la migración."
			)

	for model_name, field_names in ARCHIVED_FIELDS.items():
		model = apps.get_model("tracker", model_name)
		for field_name in field_names:
			_remove_column(schema_editor, model, field_name)

	user_table = apps.get_model("tracker", "Usuario")._meta.db_table
	user_columns = _columns(connection, user_table)
	quote_name = schema_editor.quote_name
	for column_name in ("first_name", "last_name"):
		if column_name in user_columns:
			schema_editor.execute(
				f"ALTER TABLE {quote_name(user_table)} "
				f"DROP COLUMN {quote_name(column_name)}"
			)

	if old_content_type is not None:
		codename_map = {
			"add_user": "add_usuario",
			"change_user": "change_usuario",
			"delete_user": "delete_usuario",
			"view_user": "view_usuario",
		}
		permissions = permission_model.objects.using(alias).filter(
			content_type_id=old_content_type.pk
		)
		for permission in permissions:
			new_codename = codename_map.get(permission.codename)
			if new_codename:
				permission.codename = new_codename
				permission.save(using=alias, update_fields=["codename"])
		old_content_type.app_label = "tracker"
		old_content_type.model = "usuario"
		old_content_type.save(using=alias, update_fields=["app_label", "model"])


class Migration(migrations.Migration):
	atomic = False

	replaces = [
		("tracker", "0004_update_existing_schema"),
		("tracker", "0005_ensure_perfilusuario_table"),
		("tracker", "0006_usuarioentrenamiento_activa"),
	]

	dependencies = [("tracker", "0001_squashed_initial")]

	operations = [
		migrations.RunPython(update_existing_schema),
		migrations.AddField(
			model_name="usuarioentrenamiento",
			name="activa",
			field=models.BooleanField(default=True),
		),
	]