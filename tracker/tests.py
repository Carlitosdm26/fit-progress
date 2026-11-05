from datetime import datetime
from decimal import Decimal
from importlib import import_module

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection, IntegrityError
from django.db.models.deletion import ProtectedError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
	DatoArchivado,
	Ejercicio,
	Entrenamiento,
	EntrenamientoEjercicio,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


class SeguimientoModelTests(TestCase):
	def setUp(self):
		self.usuario = get_user_model().objects.create_user(
			username="ana", email="ana@example.com", password="UnaClaveSegura123!"
		)
		self.entrenamiento = Entrenamiento.objects.create(nombre="Pierna")
		self.ejercicio = Ejercicio.objects.create(
			nombre="Sentadilla", grupo_muscular="Piernas"
		)
		self.asignacion = UsuarioEntrenamiento.objects.create(
			usuario=self.usuario, entrenamiento=self.entrenamiento
		)
		self.entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
			entrenamiento=self.entrenamiento, ejercicio=self.ejercicio, orden=1
		)
		self.ejercicio_elegido = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=self.asignacion,
			entrenamiento_ejercicio=self.entrenamiento_ejercicio,
		)
		self.sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=self.asignacion,
			fecha=timezone.make_aware(datetime(2026, 9, 16)),
		)

	def test_registra_serie_con_peso_decimal(self):
		serie = Serie.objects.create(
			sesion_entrenamiento=self.sesion,
			usuario_entrenamiento_ejercicio=self.ejercicio_elegido,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("62.50"),
		)

		self.assertEqual(serie.peso, Decimal("62.50"))

	def test_no_permite_series_duplicadas_en_una_sesion(self):
		datos = {
			"sesion_entrenamiento": self.sesion,
			"usuario_entrenamiento_ejercicio": self.ejercicio_elegido,
			"numero_serie": 1,
			"repeticiones": 8,
			"peso": Decimal("60.00"),
		}
		Serie.objects.create(**datos)

		with self.assertRaises(IntegrityError):
			Serie.objects.create(**datos)

	def test_no_permite_asignar_la_misma_rutina_dos_veces(self):
		with self.assertRaises(IntegrityError):
			UsuarioEntrenamiento.objects.create(
				usuario=self.usuario, entrenamiento=self.entrenamiento
			)

	def test_no_se_puede_borrar_ejercicio_con_historial(self):
		Serie.objects.create(
			sesion_entrenamiento=self.sesion,
			usuario_entrenamiento_ejercicio=self.ejercicio_elegido,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("60.00"),
		)

		with self.assertRaises(ProtectedError):
			self.ejercicio.delete()


class AutenticacionYRutinasTests(TestCase):
	def test_cuenta_activa_sin_grupo_tiene_perfil_deportivo(self):
		cuenta = get_user_model().objects.create_user(
			username="sin-perfil",
			email="sin-perfil@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(cuenta)

		respuesta = self.client.get(reverse("dashboard"))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Hola sin-perfil")
		self.assertNotContains(respuesta, "Hola Sin perfil")

	def test_registro_publico_esta_disponible(self):
		respuesta = self.client.get("/registro/")

		self.assertEqual(respuesta.status_code, 200)

	def test_usuario_puede_crear_entrenamiento_con_ejercicios(self):
		cuenta = get_user_model().objects.create_user(
			username="carlos@example.com",
			email="carlos@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = cuenta
		ejercicio = Ejercicio.objects.create(
			nombre="Press banca", grupo_muscular="Pecho", activo=True
		)
		self.client.force_login(cuenta)

		respuesta = self.client.post(
			reverse("crear_entrenamiento"),
			{"nombre": "Pecho fuerte", "descripcion": "Rutina inicial", "ejercicios": [ejercicio.pk]},
		)

		self.assertRedirects(respuesta, reverse("dashboard"))
		asignacion = UsuarioEntrenamiento.objects.get(usuario=perfil)
		self.assertEqual(asignacion.entrenamiento.nombre, "Pecho fuerte")
		self.assertEqual(asignacion.ejercicios_elegidos.count(), 1)

	def test_editar_rutina_muestra_marcados_los_ejercicios_asignados(self):
		cuenta = get_user_model().objects.create_user(
			username="rutina@example.com",
			email="rutina@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = cuenta
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina existente")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio_asignado = Ejercicio.objects.create(
			nombre="Press banca", grupo_muscular="Pecho"
		)
		EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio_asignado, orden=1
		)
		ejercicio_no_asignado = Ejercicio.objects.create(
			nombre="Sentadilla", grupo_muscular="Piernas"
		)
		self.client.force_login(cuenta)

		respuesta = self.client.get(
			reverse("editar_entrenamiento", args=[asignacion.pk])
		)

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(
			respuesta,
			f'name="ejercicios" value="{ejercicio_asignado.pk}" checked',
			html=False,
		)
		self.assertNotContains(
			respuesta,
			f'name="ejercicios" value="{ejercicio_no_asignado.pk}" checked',
			html=False,
		)

	def test_usuario_puede_iniciar_sesion_con_email_sin_orden_de_mayusculas(self):
		cuenta = get_user_model().objects.create_user(
			username="carlos@example.com",
			email="carlos@example.com",
			password="UnaClaveSegura123!",
		)

		respuesta = self.client.post(
			reverse("login"),
			{"username": "CARLOS@EXAMPLE.COM", "password": "UnaClaveSegura123!"},
			follow=True,
		)

		self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
		self.assertRedirects(respuesta, reverse("inicio"))

	def test_usuario_inactivo_puede_iniciar_sesion_y_solo_ve_mensaje(self):
		get_user_model().objects.create_user(
			username="inactivo",
			email="inactivo@example.com",
			password="UnaClaveSegura123!",
			is_active=False,
		)

		respuesta = self.client.post(
			reverse("login"),
			{"username": "inactivo", "password": "UnaClaveSegura123!"},
			follow=True,
		)

		self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
		self.assertEqual(respuesta.status_code, 403)
		self.assertContains(respuesta, "Tu cuenta no está activa.", status_code=403)
		self.assertNotContains(respuesta, "Ejercicios", status_code=403)

		respuesta = self.client.get(reverse("ejercicios"))

		self.assertEqual(respuesta.status_code, 403)
		self.assertContains(respuesta, "Tu cuenta no está activa.", status_code=403)

	def test_registro_publico_crea_cuenta_activa(self):
		respuesta = self.client.post(
			reverse("register"),
			{
				"username": "nuevo.usuario",
				"email": "nuevo@example.com",
				"password1": "UnaClaveSegura123!",
				"password2": "UnaClaveSegura123!",
			},
			follow=True,
		)
		cuenta = get_user_model().objects.get(email="nuevo@example.com")
		self.assertTrue(cuenta.is_active)
		self.assertTrue(respuesta.wsgi_request.user.is_authenticated)
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Hola nuevo.usuario")

	def test_admin_puede_ver_descripcion_del_usuario_y_no_nombres(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin", email="admin@example.com", password="UnaClaveSegura123!"
		)
		cuenta = get_user_model().objects.create_user(
			username="usuario", email="usuario@example.com", password="UnaClaveSegura123!"
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(f"/admin/tracker/usuario/{cuenta.pk}/change/")

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, 'name="perfil_admin-0-descripcion"')
		self.assertNotContains(respuesta, 'name="first_name"')
		self.assertNotContains(respuesta, 'name="last_name"')

	def test_login_fallido_se_registra_en_logs(self):
		get_user_model().objects.create_user(
			username="carlos",
			email="carlos@example.com",
			password="UnaClaveSegura123!",
		)

		with self.assertLogs("tracker", level="WARNING") as captured:
			self.client.post(
				reverse("login"),
				{"username": "carlos", "password": "password-mala"},
			)

		self.assertTrue(any("Intento de login fallido" in mensaje for mensaje in captured.output))
		self.assertTrue(any("username=carlos" in mensaje for mensaje in captured.output))

		with self.assertLogs("tracker", level="WARNING") as captured:
			self.client.post(
				reverse("login"),
				{"username": "usuario_inexistente", "password": "UnaClaveSegura123!"},
			)

		self.assertTrue(any("usuario_inexistente" in mensaje for mensaje in captured.output))

	def test_catalogo_requiere_login(self):
		respuesta = self.client.get(reverse("ejercicios"))

		self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('ejercicios')}")

	def test_usuario_activo_puede_anadir_ejercicio_desde_el_catalogo(self):
		cuenta = get_user_model().objects.create_user(
			username="catalogo@example.com",
			email="catalogo@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(cuenta)

		respuesta = self.client.post(
			reverse("ejercicios"),
			{
				"nombre": "Prensa de piernas",
				"grupo_muscular": "Cuádriceps",
				"equipamiento": "Máquina de prensa",
				"descripcion": "3 series de 10 repeticiones.",
			},
		)

		ejercicio = Ejercicio.objects.get(nombre="Prensa de piernas")
		self.assertRedirects(respuesta, reverse("ejercicios"))
		self.assertTrue(ejercicio.activo)
		self.assertEqual(ejercicio.grupo_muscular, "Cuádriceps")
		self.assertEqual(ejercicio.equipamiento, "Máquina de prensa")

	def test_catalogo_rechaza_ejercicio_duplicado_sin_distinguir_mayusculas(self):
		Ejercicio.objects.create(nombre="Sentadilla libre", grupo_muscular="Cuádriceps")
		cuenta = get_user_model().objects.create_user(
			username="duplicado@example.com",
			email="duplicado@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(cuenta)

		respuesta = self.client.post(
			reverse("ejercicios"),
			{
				"nombre": "SENTADILLA LIBRE",
				"grupo_muscular": "Cuádriceps",
				"equipamiento": "Barra",
				"descripcion": "3 series de 10.",
			},
		)

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Ya existe un ejercicio con ese nombre.")
		self.assertEqual(Ejercicio.objects.count(), 1)

	def test_usuario_puede_registrar_repeticiones_y_peso(self):
		cuenta = get_user_model().objects.create_user(
			username="ines@example.com",
			email="ines@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = cuenta
		entrenamiento = Entrenamiento.objects.create(nombre="Pierna")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Sentadilla", grupo_muscular="Piernas")
		entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrenamiento_ejercicio,
		)
		self.client.force_login(cuenta)

		respuesta = self.client.post(
			reverse("registrar_sesion", args=[asignacion.pk]),
			{
				"ejercicio": seleccion.pk,
				"numero_series": "2",
				"reps_1": "8",
				"peso_1": "60.50",
				"reps_2": "6",
				"peso_2": "65.00",
				"notas": "Buena sesión",
			},
		)

		sesion = SesionEntrenamiento.objects.get(usuario_entrenamiento=asignacion)
		self.assertRedirects(respuesta, reverse("editar_sesion", args=[sesion.pk]))
		self.assertEqual(sesion.series.count(), 2)
		self.assertEqual(sesion.series.get(numero_serie=1).peso, Decimal("60.50"))

		ejercicio_dos = Ejercicio.objects.create(nombre="Prensa", grupo_muscular="Piernas")
		entrenamiento_ejercicio_dos = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio_dos, orden=2
		)
		seleccion_dos = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrenamiento_ejercicio_dos,
		)
		respuesta = self.client.post(
			reverse("editar_sesion", args=[sesion.pk]),
			{
				"ejercicio": seleccion_dos.pk,
				"numero_series": "1",
				"reps_1": "10",
				"peso_1": "80.00",
				"notas": "Segundo ejercicio",
			},
		)
		self.assertRedirects(respuesta, reverse("editar_sesion", args=[sesion.pk]))
		self.assertEqual(sesion.series.count(), 3)

		respuesta = self.client.post(
			reverse("eliminar_ejercicio_sesion", args=[sesion.pk, seleccion_dos.pk])
		)
		self.assertRedirects(respuesta, reverse("editar_sesion", args=[sesion.pk]))
		self.assertEqual(sesion.series.count(), 2)

		respuesta = self.client.post(reverse("eliminar_sesion", args=[sesion.pk]))
		self.assertRedirects(respuesta, reverse("dashboard"))
		self.assertFalse(SesionEntrenamiento.objects.filter(pk=sesion.pk).exists())

	def test_se_muestran_los_ejercicios_guardados_even_si_ya_no_quedan_por_aniadir(self):
		cuenta = get_user_model().objects.create_user(
			username="eva@example.com", email="eva@example.com", password="UnaClaveSegura123!"
		)
		perfil = cuenta
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina falsos")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Remo", grupo_muscular="Espalda")
		entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrenamiento_ejercicio,
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now(),
		)
		Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("50.00"),
		)
		self.client.force_login(cuenta)

		respuesta = self.client.get(reverse("editar_sesion", args=[sesion.pk]))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Ejercicios guardados")
		self.assertContains(respuesta, "Remo")
		self.assertContains(respuesta, "Ya has registrado todos los ejercicios de esta sesión.")
		self.assertContains(
			respuesta,
			reverse("registrar_sesion", args=[asignacion.pk]),
		)

		respuesta = self.client.get(reverse("registrar_sesion", args=[asignacion.pk]))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Remo")
		self.assertNotContains(respuesta, "Ya has registrado todos los ejercicios")

	def test_usuario_puede_editar_rutina(self):
		cuenta = get_user_model().objects.create_user(
			username="eva@example.com", email="eva@example.com", password="UnaClaveSegura123!"
		)
		perfil = cuenta
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina antigua")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Remo", grupo_muscular="Espalda")
		self.client.force_login(cuenta)

		respuesta = self.client.post(
			reverse("editar_entrenamiento", args=[asignacion.pk]),
			{"nombre": "Rutina espalda", "descripcion": "Actualizada", "ejercicios": [ejercicio.pk]},
		)

		self.assertRedirects(respuesta, reverse("dashboard"))
		entrenamiento.refresh_from_db()
		self.assertEqual(entrenamiento.nombre, "Rutina espalda")
		self.assertEqual(entrenamiento.ejercicios.count(), 1)

	def test_inicio_muestra_estadisticas_y_historial_de_sesiones(self):
		cuenta = get_user_model().objects.create_user(
			username="lucia@example.com", email="lucia@example.com", password="UnaClaveSegura123!"
		)
		perfil = cuenta
		entrenamiento = Entrenamiento.objects.create(nombre="Full body")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Peso muerto", grupo_muscular="Espalda")
		entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrenamiento_ejercicio,
		)
		self.client.force_login(cuenta)

		sesion_hoy = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now(),
			notas="Sesión buena y con mucha fuerza.",
		)
		SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now() - timezone.timedelta(days=12),
			notas="Otra sesión.",
		)
		SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now() - timezone.timedelta(days=45),
			notas="Hace tiempo.",
		)
		Serie.objects.create(
			sesion_entrenamiento=sesion_hoy,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=5,
			peso=Decimal("70.00"),
		)
		Serie.objects.create(
			sesion_entrenamiento=sesion_hoy,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=2,
			repeticiones=4,
			peso=Decimal("75.00"),
		)
		respuesta = self.client.get(reverse("dashboard"))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Inicio")
		self.assertContains(respuesta, "Días trabajados")
		self.assertContains(respuesta, "Sesiones en los últimos 30 días")
		self.assertContains(respuesta, "Series en los últimos 30 días")
		self.assertContains(respuesta, "Últimas 5 sesiones")
		self.assertContains(respuesta, "Ver historial completo")
		self.assertContains(respuesta, "Sesión buena y con mucha fuerza.")

	def test_sesion_muestra_notas_en_la_pantalla_de_edicion(self):
		cuenta = get_user_model().objects.create_user(
			username="marta@example.com", email="marta@example.com", password="UnaClaveSegura123!"
		)
		perfil = cuenta
		entrenamiento = Entrenamiento.objects.create(nombre="Bíceps")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Curl", grupo_muscular="Brazos")
		entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrenamiento_ejercicio,
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now(),
			notas="Notas del entrenamiento: control de tempo.",
		)
		Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=10,
			peso=Decimal("20.00"),
		)
		self.client.force_login(cuenta)

		respuesta = self.client.get(reverse("editar_sesion", args=[sesion.pk]))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Notas del entrenamiento: control de tempo.")


class ActualizacionEsquemaTests(TransactionTestCase):
	def test_migraciones_antiguas_se_reconocen_como_esquema_consolidado(self):
		recorder = MigrationRecorder(connection)
		recorder.record_unapplied("tracker", "0001_squashed_initial")
		legacy_migrations = (
			"0001_initial",
			"0002_usuario_cuenta",
			"0003_unify_user_table",
		)
		try:
			for migration_name in legacy_migrations:
				recorder.record_applied("tracker", migration_name)
			loader = MigrationExecutor(connection).loader
			self.assertIn(("tracker", "0001_squashed_initial"), loader.applied_migrations)
			self.assertIn(("tracker", "0004_update_existing_schema"), loader.graph.nodes)
		finally:
			for migration_name in legacy_migrations:
				recorder.record_unapplied("tracker", migration_name)
			recorder.record_applied("tracker", "0001_squashed_initial")

	def test_actualiza_columnas_sin_perder_registros_ni_permisos(self):
		tables = set(connection.introspection.table_names())
		self.assertNotIn("tracker_usuario", tables)
		with connection.cursor() as cursor:
			user_columns = {
				column.name
				for column in connection.introspection.get_table_description(
					cursor, "auth_user"
				)
			}
		self.assertNotIn("first_name", user_columns)
		self.assertNotIn("last_name", user_columns)

		user = get_user_model().objects.create_user(
			username="migracion",
			email="migracion@example.com",
			password="UnaClaveSegura123!",
		)
		group = Group.objects.create(name="Grupo migración")
		content_type = ContentType.objects.get(app_label="tracker", model="usuario")
		permission = Permission.objects.get(
			content_type=content_type, codename="add_usuario"
		)
		user.groups.add(group)
		user.user_permissions.add(permission)
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina migración")
		ejercicio = Ejercicio.objects.create(nombre="Sentadilla", grupo_muscular="Piernas")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=user, entrenamiento=entrenamiento
		)
		entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrenamiento_ejercicio,
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now(),
			notas="Conservar nota de sesión",
		)
		serie = Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("60.00"),
		)

		quote_name = connection.ops.quote_name
		legacy_columns = {
			"auth_user": ("first_name", "last_name"),
			"tracker_entrenamiento": ("notas",),
			"tracker_entrenamientoejercicio": ("notas",),
			"tracker_usuarioentrenamientoejercicio": ("notas",),
			"tracker_serie": ("notas",),
		}
		with connection.schema_editor() as schema_editor:
			for table_name, columns in legacy_columns.items():
				for column_name in columns:
					schema_editor.execute(
						f"ALTER TABLE {quote_name(table_name)} ADD COLUMN "
						f"{quote_name(column_name)} TEXT NOT NULL DEFAULT ''"
					)
		with connection.cursor() as cursor:
			cursor.execute(
				'UPDATE "auth_user" SET first_name = %s, last_name = %s WHERE id = %s',
				["Nombre antiguo", "Apellido antiguo", user.pk],
			)
			for table_name, columns in legacy_columns.items():
				if table_name == "auth_user":
					continue
				cursor.execute(
					f"UPDATE {quote_name(table_name)} SET notas = %s WHERE id = %s",
					["Nota anterior", {
						"tracker_entrenamiento": entrenamiento.pk,
						"tracker_entrenamientoejercicio": entrenamiento_ejercicio.pk,
						"tracker_usuarioentrenamientoejercicio": seleccion.pk,
						"tracker_serie": serie.pk,
					}[table_name]],
				)

		content_type.app_label = "auth"
		content_type.model = "user"
		content_type.save(update_fields=["app_label", "model"])
		permission.codename = "add_user"
		permission.save(update_fields=["codename"])

		migration_apps = MigrationExecutor(connection).loader.project_state(
			[("tracker", "0001_squashed_initial")]
		).apps
		migration = import_module("tracker.migrations.0004_update_existing_schema")
		with connection.schema_editor() as schema_editor:
			migration.update_existing_schema(migration_apps, schema_editor)

		user.refresh_from_db()
		self.assertEqual(user.username, "migracion")
		self.assertTrue(user.check_password("UnaClaveSegura123!"))
		self.assertIn(group, user.groups.all())
		self.assertTrue(user.has_perm("tracker.add_usuario"))
		self.assertTrue(SesionEntrenamiento.objects.filter(pk=sesion.pk).exists())
		self.assertTrue(Serie.objects.filter(pk=serie.pk, peso=Decimal("60.00")).exists())
		self.assertEqual(SesionEntrenamiento.objects.get(pk=sesion.pk).notas, "Conservar nota de sesión")
		self.assertEqual(DatoArchivado.objects.filter(valor="Nota anterior").count(), 4)

		for table_name, columns in legacy_columns.items():
			with connection.cursor() as cursor:
				table_columns = {
					column.name
					for column in connection.introspection.get_table_description(
						cursor, table_name
					)
				}
			for column_name in columns:
				self.assertNotIn(column_name, table_columns)
