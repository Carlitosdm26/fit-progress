from django.db import migrations


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


def _archive_and_remove_column(apps, schema_editor, archive_model, model, field_name):
    connection = schema_editor.connection
    table_name = model._meta.db_table
    column_name = field_name
    columns = _columns(connection, table_name)
    if column_name not in columns:
        return

    quote_name = schema_editor.quote_name
    select_sql = (
        f"SELECT {quote_name(model._meta.pk.column)}, {quote_name(column_name)} "
        f"FROM {quote_name(table_name)} "
        f"WHERE {quote_name(column_name)} IS NOT NULL "
        f"AND {quote_name(column_name)} <> %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(select_sql, [""])
        while rows := cursor.fetchmany(500):
            archive_model.objects.using(connection.alias).bulk_create(
                [
                    archive_model(
                        modelo=f"tracker.{model._meta.model_name}",
                        registro_id=record_id,
                        campo=field_name,
                        valor=value,
                    )
                    for record_id, value in rows
                ],
                batch_size=500,
                ignore_conflicts=True,
            )

    schema_editor.execute(
        f"ALTER TABLE {quote_name(table_name)} DROP COLUMN {quote_name(column_name)}"
    )


def update_existing_schema(apps, schema_editor):
    connection = schema_editor.connection
    alias = connection.alias
    tables = set(connection.introspection.table_names())
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

    profile_model = apps.get_model("tracker", "PerfilUsuario")
    archive_model = apps.get_model("tracker", "DatoArchivado")

    for model in (profile_model, archive_model):
        if model._meta.db_table not in tables:
            schema_editor.create_model(model)
            tables.add(model._meta.db_table)

    for model_name, field_names in ARCHIVED_FIELDS.items():
        model = apps.get_model("tracker", model_name)
        for field_name in field_names:
            _archive_and_remove_column(
                apps, schema_editor, archive_model, model, field_name
            )

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

    dependencies = [("tracker", "0001_squashed_initial")]

    operations = [migrations.RunPython(update_existing_schema)]
