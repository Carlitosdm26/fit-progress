from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models
import django.db.models.deletion


FITNESS_USER_GROUP_NAME = "Usuarios de gimnasio"


def migrate_fitness_users(apps, schema_editor):
	User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
	Group = apps.get_model("auth", "Group")
	Profile = apps.get_model("tracker", "Usuario")
	Assignment = apps.get_model("tracker", "UsuarioEntrenamiento")
	database = schema_editor.connection.alias

	users = User.objects.using(database)
	profiles = Profile.objects.using(database).order_by("pk")
	group, _ = Group.objects.using(database).get_or_create(
		name=FITNESS_USER_GROUP_NAME
	)
	used_user_ids = set()
	profile_user_ids = {}
	normalized_emails = set()

	for profile in profiles:
		normalized_email = profile.email.strip().casefold()
		if normalized_email and normalized_email in normalized_emails:
			raise RuntimeError(
				"Hay perfiles con emails duplicados sin distinguir mayúsculas. "
				"Corrige esos emails antes de aplicar esta migración."
			)
		if normalized_email:
			normalized_emails.add(normalized_email)

		if profile.cuenta_id:
			user = users.get(pk=profile.cuenta_id)
			email_matches = list(
				users.filter(email__iexact=profile.email).exclude(pk=user.pk).values_list(
					"pk", flat=True
				)
			)
			if email_matches:
				raise RuntimeError(
					f"El email {profile.email!r} también pertenece a otra cuenta. "
					"Resuelve el email duplicado antes de aplicar esta migración."
				)
		else:
			email_matches = list(
				users.filter(email__iexact=profile.email).values_list("pk", flat=True)
			) if profile.email else []
			if len(email_matches) > 1:
				raise RuntimeError(
					f"Hay varias cuentas con el email {profile.email!r}; "
					"vincula el perfil a la cuenta correcta antes de migrar."
				)
			if email_matches:
				user = users.get(pk=email_matches[0])
			else:
				username_limit = User._meta.get_field("username").max_length
				username_base = profile.email[:username_limit] or f"usuario-{profile.pk}"
				username = username_base
				suffix = 1
				while users.filter(username__iexact=username).exists():
					suffix += 1
					suffix_text = f"-{suffix}"
					username = f"{username_base[:username_limit - len(suffix_text)]}{suffix_text}"
				user = User(
					username=username,
					email=profile.email,
					date_joined=profile.fecha_registro,
					is_active=profile.activo,
				)
				user.password = make_password(None)
				user.save(using=database)

		if user.pk in used_user_ids:
			raise RuntimeError(
				f"Más de un perfil está asociado a la misma cuenta (ID {user.pk}). "
				"Corrige las asociaciones antes de aplicar esta migración."
			)
		used_user_ids.add(user.pk)
		user.first_name = profile.nombre
		user.email = profile.email
		user.save(
			using=database,
			update_fields=["first_name", "email"],
		)
		group.user_set.db_manager(database).add(user)
		profile_user_ids[profile.pk] = user.pk

	if profile_user_ids:
		table = Assignment._meta.db_table
		column = Assignment._meta.get_field("usuario").column
		quote_name = schema_editor.quote_name
		old_ids = list(profile_user_ids)
		case_sql = " ".join("WHEN %s THEN %s" for _ in old_ids)
		parameters = [
			value
			for profile_id, user_id in profile_user_ids.items()
			for value in (profile_id, user_id)
		]
		parameters.extend(old_ids)
		with schema_editor.connection.cursor() as cursor:
			cursor.execute(
				f"UPDATE {quote_name(table)} "
				f"SET {quote_name(column)} = CASE {quote_name(column)} {case_sql} "
				f"ELSE {quote_name(column)} END "
				f"WHERE {quote_name(column)} IN ({', '.join('%s' for _ in old_ids)})",
				parameters,
			)


class Migration(migrations.Migration):

	dependencies = [
		("tracker", "0002_usuario_cuenta"),
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.AlterField(
			model_name="usuarioentrenamiento",
			name="usuario",
			field=models.ForeignKey(
				db_constraint=False,
				on_delete=django.db.models.deletion.CASCADE,
				related_name="entrenamientos",
				to=settings.AUTH_USER_MODEL,
			),
		),
		migrations.RunPython(migrate_fitness_users),
		migrations.AlterField(
			model_name="usuarioentrenamiento",
			name="usuario",
			field=models.ForeignKey(
				on_delete=django.db.models.deletion.CASCADE,
				related_name="entrenamientos",
				to=settings.AUTH_USER_MODEL,
			),
		),
		migrations.DeleteModel(name="Usuario"),
	]
