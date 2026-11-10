from datetime import datetime
from decimal import Decimal

from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.contrib.auth.models import Group
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
	Ejercicio,
	Entrenamiento,
	EntrenamientoEjercicio,
	PerfilUsuario,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


def vincular_usuario_gimnasio(user, _nombre):
	return user


class SeguimientoModelTests(TestCase):
	def setUp(self):
		self.usuario = vincular_usuario_gimnasio(
			get_user_model().objects.create_user(
				username="ana", email="ana@example.com", password="UnaClaveSegura123!"
			),
			"Ana",
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

	def test_una_rutina_no_puede_tener_dos_propietarios(self):
		otro_usuario = get_user_model().objects.create_user(
			username="otra-persona", email="otra@example.com"
		)
		with self.assertRaises(IntegrityError):
			UsuarioEntrenamiento.objects.create(
				usuario=otro_usuario, entrenamiento=self.entrenamiento
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
	def test_admin_puede_abrir_edicion_de_usuario(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		user = get_user_model().objects.create_user(
			username="usuario",
			email="usuario@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(
			reverse("panel_admin:usuario_editar", args=[user.pk])
		)

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "usuario@example.com")

		respuesta = self.client.get(
			reverse("panel_admin:usuario_detalle", args=[user.pk])
		)
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Editar usuario")
		self.assertNotContains(respuesta, "Guardar cambios")
		respuesta = self.client.get(reverse("panel_admin:usuarios"))
		self.assertContains(respuesta, "Ver")
		self.assertContains(
			respuesta,
			reverse("panel_admin:usuario_detalle", args=[user.pk]),
		)

		PerfilUsuario.objects.create(usuario=user, descripcion="Perfil de prueba")
		respuesta = self.client.get(
			reverse("panel_admin:usuario_detalle", args=[user.pk])
		)
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "usuario@example.com")

	def test_panel_admin_requires_staff(self):
		url = reverse("panel_admin:inicio")
		respuesta = self.client.get(url)
		self.assertRedirects(respuesta, f"{reverse('login')}?next={url}")

		cuenta = get_user_model().objects.create_user(
			username="cuenta",
			email="cuenta@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(cuenta)
		respuesta = self.client.get(url)
		self.assertRedirects(respuesta, reverse("inicio"))

		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(admin_user)
		respuesta = self.client.get(url)
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Cuentas registradas")
		self.assertContains(respuesta, "Abrir menú de administración")
		self.assertContains(respuesta, "Volver al área cliente")
		self.assertContains(respuesta, ".menu-toggle { display: block; }")
		self.assertContains(
			respuesta, '<path d="M3 6h18M3 12h18M3 18h18"></path>'
		)
		html = respuesta.content.decode()
		self.assertLess(
			html.index('<header class="topline">'),
			html.index('<button class="menu-toggle"'),
		)

	def test_menu_cliente_es_desplegable_y_separa_administracion(self):
		usuario = get_user_model().objects.create_user(
			username="cliente",
			email="cliente@example.com",
		)
		self.client.force_login(usuario)

		respuesta = self.client.get(reverse("inicio"))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "Abrir menú de cliente")
		self.assertContains(respuesta, 'aria-controls="client-navigation"')
		self.assertContains(respuesta, "Área cliente")
		self.assertContains(respuesta, ">Sesiones</a>")
		self.assertNotContains(respuesta, ">Historial</a>")
		self.assertNotContains(respuesta, 'class="admin-nav-link"')
		self.assertContains(respuesta, ".nav-links.is-open { display: flex; }")
		self.assertContains(
			respuesta,
			".button.danger { border: 1px solid #a52b23; background: var(--green); color: #a52b23; }",
		)

		usuario.is_staff = True
		usuario.save(update_fields=["is_staff"])
		respuesta = self.client.get(reverse("inicio"))

		self.assertContains(respuesta, 'class="admin-nav-link"')
		self.assertContains(respuesta, "Administración")

	def test_staff_no_puede_conceder_privilegios_ni_editar_superusuarios(self):
		staff_user = get_user_model().objects.create_user(
			username="staff",
			email="staff@example.com",
			password="UnaClaveSegura123!",
			is_staff=True,
		)
		superuser = get_user_model().objects.create_superuser(
			username="root",
			email="root@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(staff_user)

		respuesta = self.client.get(reverse("panel_admin:usuario_nuevo"))
		self.assertNotContains(respuesta, "Permisos totales")
		self.assertNotContains(respuesta, "Acceso al panel")

		respuesta = self.client.post(
			reverse("panel_admin:usuario_nuevo"),
			{
				"username": "sin-privilegios",
				"email": "normal@example.com",
				"password1": "jR9!wV4#qT8@zK2",
				"password2": "jR9!wV4#qT8@zK2",
				"is_staff": "on",
				"is_superuser": "on",
			},
		)
		creado = get_user_model().objects.get(username="sin-privilegios")
		self.assertFalse(creado.is_staff)
		self.assertFalse(creado.is_superuser)
		self.assertEqual(
			self.client.get(
				reverse("panel_admin:usuario_editar", args=[superuser.pk])
			).status_code,
			403,
		)

	def test_login_retorna_al_panel_solicitado(self):
		cuenta = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		respuesta = self.client.post(
			reverse("login"),
			{
				"username": cuenta.username,
				"password": "UnaClaveSegura123!",
				"next": reverse("panel_admin:inicio"),
			},
		)
		self.assertRedirects(respuesta, reverse("panel_admin:inicio"))

	def test_panel_admin_busca_y_crea_usuarios(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		get_user_model().objects.create_user(
			username="maratonista",
			email="runner@example.com",
			password="UnaClaveSegura123!",
		)
		get_user_model().objects.create_user(
			username="ciclista",
			email="bike@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(reverse("panel_admin:usuarios"), {"q": "runner"})
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "maratonista")
		self.assertNotContains(respuesta, "ciclista")

		respuesta = self.client.post(
			reverse("panel_admin:usuario_nuevo"),
			{
				"username": "nueva-cuenta",
				"email": "nuevo@example.com",
				"is_active": "on",
				"password1": "jR9!wV4#qT8@zK2",
				"password2": "jR9!wV4#qT8@zK2",
			},
		)
		cuenta = get_user_model().objects.get(username="nueva-cuenta")
		self.assertRedirects(
			respuesta, reverse("panel_admin:usuario_detalle", args=[cuenta.pk])
		)
		self.assertTrue(cuenta.check_password("jR9!wV4#qT8@zK2"))

	def test_panel_admin_conecta_usuarios_rutinas_y_ejercicios(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		usuario = get_user_model().objects.create_user(
			username="maratonista",
			email="runner@example.com",
			password="UnaClaveSegura123!",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Fuerza A")
		ejercicio = Ejercicio.objects.create(nombre="Sentadilla", grupo_muscular="Piernas")
		entrada_plantilla = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(reverse("panel_admin:usuario_editar", args=[usuario.pk]))
		self.assertNotContains(respuesta, "Fuerza A")
		respuesta = self.client.get(
			reverse("panel_admin:usuario_detalle", args=[usuario.pk])
		)
		self.assertNotContains(respuesta, "Fuerza A")
		respuesta = self.client.get(
			reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk])
		)
		self.assertContains(respuesta, "Sentadilla")

		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk]),
			{"action": "asignar_usuario", "usuario": usuario.pk},
		)
		self.assertEqual(respuesta.status_code, 302)
		asignacion = UsuarioEntrenamiento.objects.get(usuario=usuario)
		self.assertNotEqual(asignacion.entrenamiento_id, entrenamiento.pk)
		self.assertEqual(asignacion.entrenamiento.rutina_origen_id, entrenamiento.pk)
		entrada_personal = asignacion.entrenamiento.ejercicios.get()
		self.assertEqual(entrada_personal.ejercicio, ejercicio)

		respuesta = self.client.post(
			reverse("panel_admin:ejercicio_nuevo"),
			{
				"nombre": "Peso muerto",
				"grupo_muscular": "Espalda",
				"equipamiento": "Barra",
				"descripcion": "Técnica controlada",
				"activo": "on",
			},
		)
		ejercicio_nuevo = Ejercicio.objects.get(nombre="Peso muerto")
		self.assertEqual(respuesta.status_code, 302)

		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk]),
			{"action": "anadir_ejercicio", "ejercicio": ejercicio_nuevo.pk, "orden": 2},
		)
		self.assertEqual(respuesta.status_code, 302)
		entrada_nueva = EntrenamientoEjercicio.objects.get(
			entrenamiento=entrenamiento, ejercicio=ejercicio_nuevo
		)
		self.assertFalse(
			UsuarioEntrenamientoEjercicio.objects.filter(
				usuario_entrenamiento=asignacion,
				entrenamiento_ejercicio__ejercicio=ejercicio_nuevo,
			).exists()
		)
		self.assertEqual(asignacion.entrenamiento.ejercicios.count(), 1)

		nuevo_usuario = get_user_model().objects.create_user(
			username="ciclista",
			email="bike@example.com",
			password="UnaClaveSegura123!",
		)
		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk]),
			{"action": "asignar_usuario", "usuario": nuevo_usuario.pk},
		)
		self.assertEqual(respuesta.status_code, 302)
		nueva_asignacion = UsuarioEntrenamiento.objects.get(usuario=nuevo_usuario)
		self.assertEqual(nueva_asignacion.entrenamiento.rutina_origen_id, entrenamiento.pk)
		self.assertNotEqual(nueva_asignacion.entrenamiento_id, asignacion.entrenamiento_id)
		self.assertEqual(nueva_asignacion.ejercicios_elegidos.count(), 2)

		respuesta = self.client.post(
			reverse("panel_admin:ejercicio_editar", args=[ejercicio_nuevo.pk]),
			{
				"nombre": "Peso muerto rumano",
				"grupo_muscular": "Espalda",
				"equipamiento": "Barra",
				"descripcion": "Técnica controlada",
				"activo": "on",
			},
		)
		ejercicio_nuevo.refresh_from_db()
		self.assertEqual(ejercicio_nuevo.nombre, "Peso muerto rumano")
		self.assertTrue(
			EntrenamientoEjercicio.objects.filter(
				entrenamiento=entrenamiento, ejercicio=ejercicio_nuevo
			).exists()
		)
		self.assertFalse(
			EntrenamientoEjercicio.objects.filter(
				entrenamiento=asignacion.entrenamiento, ejercicio=ejercicio_nuevo
			).exists()
		)

		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_ejercicio_editar", args=[entrenamiento.pk, entrada_nueva.pk]),
			{"ejercicio": ejercicio_nuevo.pk, "orden": 3},
		)
		entrada_nueva.refresh_from_db()
		self.assertRedirects(
			respuesta, reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk])
		)
		self.assertEqual(entrada_nueva.orden, 3)
		entrada_plantilla.refresh_from_db()
		self.assertEqual(entrada_plantilla.orden, 1)
		self.assertEqual(entrada_personal.orden, 1)

	def test_panel_admin_lista_rutinas_por_usuario_y_asignar_crea_copia_independiente(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="test-password-123",
		)
		usuario_origen = get_user_model().objects.create_user(
			username="origen",
			email="origen@example.com",
			password="test-password-123",
		)
		usuario_destino = get_user_model().objects.create_user(
			username="destino",
			email="destino@example.com",
			password="test-password-123",
		)
		rutina = Entrenamiento.objects.create(nombre="Tren Superior")
		ejercicio = Ejercicio.objects.create(nombre="Remo", grupo_muscular="Espalda")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=rutina, ejercicio=ejercicio, orden=1
		)
		asignacion_origen = UsuarioEntrenamiento.objects.create(
			usuario=usuario_origen, entrenamiento=rutina
		)
		UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion_origen,
			entrenamiento_ejercicio=entrada,
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(reverse("panel_admin:entrenamientos"))
		self.assertContains(respuesta, "Rutinas")
		self.assertContains(respuesta, "Tren Superior")
		self.assertContains(respuesta, "origen")
		self.assertEqual(respuesta.context["page_obj"].paginator.count, 1)

		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_detalle", args=[rutina.pk]),
			{"action": "asignar_usuario", "usuario": usuario_destino.pk},
		)
		self.assertRedirects(
			respuesta, reverse("panel_admin:entrenamiento_detalle", args=[rutina.pk])
		)
		respuesta = self.client.get(
			reverse("panel_admin:entrenamiento_detalle", args=[rutina.pk])
		)
		self.assertContains(respuesta, "origen")
		self.assertNotContains(
			respuesta,
			f'href="{reverse("panel_admin:usuario_detalle", args=[usuario_destino.pk])}">destino</a>',
		)
		asignacion_destino = UsuarioEntrenamiento.objects.get(usuario=usuario_destino)
		self.assertNotEqual(asignacion_destino.entrenamiento_id, rutina.pk)
		self.assertEqual(asignacion_destino.entrenamiento.rutina_origen_id, rutina.pk)
		self.assertEqual(asignacion_destino.entrenamiento.ejercicios.get().ejercicio, ejercicio)
		respuesta = self.client.get(reverse("panel_admin:entrenamientos"))
		self.assertContains(respuesta, "destino")
		self.assertEqual(respuesta.context["page_obj"].paginator.count, 2)
		respuesta = self.client.get(
			reverse("panel_admin:entrenamiento_detalle", args=[asignacion_destino.entrenamiento_id])
		)
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(
			respuesta,
			f'href="{reverse("panel_admin:usuario_detalle", args=[usuario_destino.pk])}">destino</a>',
		)
		self.assertNotContains(
			respuesta,
			f'href="{reverse("panel_admin:usuario_detalle", args=[usuario_origen.pk])}">origen</a>',
		)

	def test_panel_admin_lista_propietario_y_solo_usuarios_asignados_activos(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="test-password-123",
		)
		usuarios = [
			get_user_model().objects.create_user(
				username=nombre,
				email=f"{nombre}@example.com",
				password="test-password-123",
			)
			for nombre in ("activo", "desasignado")
		]
		rutina = Entrenamiento.objects.create(nombre="Full body")
		asignaciones = []
		for usuario in usuarios:
			copia = Entrenamiento.objects.create(
				nombre=rutina.nombre,
				rutina_origen=rutina,
			)
			asignaciones.append(
				UsuarioEntrenamiento.objects.create(
					usuario=usuario,
					entrenamiento=copia,
					activa=usuario.username == "activo",
				)
			)
		self.client.force_login(admin_user)

		respuesta = self.client.get(reverse("panel_admin:entrenamientos"))
		self.assertEqual(respuesta.context["page_obj"].paginator.count, 3)
		self.assertContains(respuesta, "activo")
		self.assertContains(respuesta, "Sin asignar")

		respuesta = self.client.get(
			reverse(
				"panel_admin:entrenamiento_detalle",
				args=[asignaciones[0].entrenamiento_id],
			)
		)
		usuario_activo_url = reverse("panel_admin:usuario_detalle", args=[usuarios[0].pk])
		usuario_inactivo_url = reverse(
			"panel_admin:usuario_detalle", args=[usuarios[1].pk]
		)
		self.assertContains(respuesta, f'href="{usuario_activo_url}">activo</a>')
		self.assertNotContains(respuesta, f'href="{usuario_inactivo_url}">desasignado</a>')
		self.assertContains(respuesta, "activo")

		respuesta = self.client.post(
			reverse(
				"panel_admin:entrenamiento_usuario_desasignar",
				args=[asignaciones[0].entrenamiento_id, asignaciones[0].pk],
			)
		)
		self.assertRedirects(
			respuesta,
			reverse(
				"panel_admin:entrenamiento_detalle",
				args=[asignaciones[0].entrenamiento_id],
			),
		)
		respuesta = self.client.get(
			reverse(
				"panel_admin:entrenamiento_detalle",
				args=[asignaciones[0].entrenamiento_id],
			)
		)
		self.assertContains(respuesta, "Esta rutina no está asignada actualmente.")
		self.assertNotContains(respuesta, f'href="{usuario_activo_url}">activo</a>')
		self.assertNotContains(respuesta, f'href="{usuario_inactivo_url}">desasignado</a>')
		rutina.refresh_from_db()
		self.assertEqual(rutina.copias.filter(usuarios__activa=True).count(), 0)

	def test_panel_admin_elimina_rutina_conservando_sesiones_e_historial(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="test-password",
		)
		usuario_origen = get_user_model().objects.create_user(
			username="origen",
			email="origen@example.com",
			password="test-password",
		)
		usuario_copia = get_user_model().objects.create_user(
			username="copia",
			email="copia@example.com",
			password="test-password",
		)
		rutina = Entrenamiento.objects.create(nombre="Fuerza")
		ejercicio = Ejercicio.objects.create(nombre="Press", grupo_muscular="Pecho")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=rutina, ejercicio=ejercicio, orden=1
		)
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=usuario_origen, entrenamiento=rutina
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrada,
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion, fecha=timezone.now()
		)
		serie = Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("50.00"),
		)
		rutina_copia = Entrenamiento.objects.create(
			nombre=rutina.nombre, rutina_origen=rutina
		)
		UsuarioEntrenamiento.objects.create(
			usuario=usuario_copia, entrenamiento=rutina_copia
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(reverse("panel_admin:entrenamientos"))
		self.assertContains(
			respuesta,
			reverse("panel_admin:entrenamiento_eliminar", args=[rutina.pk]),
		)
		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_eliminar", args=[rutina.pk])
		)

		self.assertRedirects(respuesta, reverse("panel_admin:entrenamientos"))
		rutina.refresh_from_db()
		asignacion.refresh_from_db()
		self.assertTrue(rutina.eliminada)
		self.assertFalse(asignacion.activa)
		self.assertTrue(SesionEntrenamiento.objects.filter(pk=sesion.pk).exists())
		self.assertTrue(Serie.objects.filter(pk=serie.pk).exists())
		rutina_copia.refresh_from_db()
		self.assertEqual(rutina_copia.rutina_origen_id, rutina.pk)
		self.assertTrue(
			UsuarioEntrenamiento.objects.filter(
				usuario=usuario_copia, entrenamiento=rutina_copia
			).exists()
		)
		respuesta = self.client.get(reverse("panel_admin:entrenamientos"))
		self.assertNotIn(
			rutina.pk,
			[item.pk for item in respuesta.context["page_obj"]],
		)
		respuesta = self.client.get(reverse("panel_admin:sesiones"))
		self.assertContains(respuesta, "Fuerza")

	def test_usuario_elimina_rutina_sin_borrar_sesiones(self):
		usuario = get_user_model().objects.create_user(
			username="cliente",
			email="cliente@example.com",
			password="test-password",
		)
		rutina = Entrenamiento.objects.create(nombre="Rutina cliente")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=usuario, entrenamiento=rutina
		)
		ejercicio = Ejercicio.objects.create(nombre="Press", grupo_muscular="Pecho")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=rutina, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrada,
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion, fecha=timezone.now()
		)
		serie = Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("50.00"),
		)
		self.client.force_login(usuario)

		respuesta = self.client.post(
			reverse("eliminar_entrenamiento", args=[asignacion.pk])
		)

		self.assertRedirects(respuesta, reverse("dashboard"))
		rutina.refresh_from_db()
		asignacion.refresh_from_db()
		self.assertTrue(rutina.eliminada)
		self.assertFalse(asignacion.activa)
		self.assertTrue(SesionEntrenamiento.objects.filter(pk=sesion.pk).exists())
		self.assertTrue(Serie.objects.filter(pk=serie.pk).exists())
		respuesta = self.client.get(reverse("historial_sesiones"))
		self.assertContains(respuesta, "Rutina cliente")
		respuesta = self.client.get(reverse("dashboard"))
		self.assertNotIn(
			asignacion.pk,
			[item.pk for item in respuesta.context["asignaciones"]],
		)

	def test_panel_admin_edita_sesiones_y_series_sin_romper_referencias(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		usuario = get_user_model().objects.create_user(
			username="usuario",
			email="usuario@example.com",
			password="UnaClaveSegura123!",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Pierna")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=usuario, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Prensa", grupo_muscular="Piernas")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion, entrenamiento_ejercicio=entrada
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion, fecha=timezone.now(), notas="Original"
		)
		self.client.force_login(admin_user)

		respuesta = self.client.get(
			reverse("panel_admin:sesiones"),
			{"usuario": usuario.pk, "rutina": entrenamiento.pk},
		)
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, "usuario")

		respuesta = self.client.post(
			reverse("panel_admin:sesion_detalle", args=[sesion.pk]),
			{
				"action": "guardar_sesion",
				"fecha": timezone.localtime(sesion.fecha).strftime("%Y-%m-%dT%H:%M"),
				"notas": "Revisada por administración",
			},
		)
		self.assertEqual(respuesta.status_code, 302)
		sesion.refresh_from_db()
		self.assertEqual(sesion.notas, "Revisada por administración")

		respuesta = self.client.post(
			reverse("panel_admin:sesion_detalle", args=[sesion.pk]),
			{
				"action": "anadir_serie",
				"usuario_entrenamiento_ejercicio": seleccion.pk,
				"numero_serie": 1,
				"repeticiones": 8,
				"peso": "70.50",
			},
		)
		self.assertEqual(respuesta.status_code, 302)
		serie = Serie.objects.get(sesion_entrenamiento=sesion)
		self.assertEqual(serie.usuario_entrenamiento_ejercicio, seleccion)
		self.assertEqual(serie.peso, Decimal("70.50"))
		segunda_serie = Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=2,
			repeticiones=6,
			peso=Decimal("75.00"),
		)

		respuesta = self.client.post(
			reverse(
				"panel_admin:entrenamiento_ejercicio_eliminar",
				args=[entrenamiento.pk, entrada.pk],
			)
		)
		self.assertEqual(respuesta.status_code, 302)
		self.assertTrue(EntrenamientoEjercicio.objects.filter(pk=entrada.pk).exists())

		respuesta = self.client.get(
			reverse("panel_admin:sesion_detalle", args=[sesion.pk])
		)
		self.assertContains(respuesta, "Prensa")
		self.assertContains(respuesta, "70,50 kg")
		self.assertContains(respuesta, "75,00 kg")
		self.assertEqual(respuesta.context["series_count"], 2)
		self.assertEqual(len(respuesta.context["series_por_ejercicio"][0]["series"]), 2)
		self.assertTrue(Serie.objects.filter(pk=segunda_serie.pk).exists())
		self.assertContains(respuesta, "Eliminar")

		respuesta = self.client.post(
			reverse("panel_admin:serie_eliminar", args=[sesion.pk, segunda_serie.pk])
		)
		self.assertRedirects(
			respuesta, reverse("panel_admin:sesion_detalle", args=[sesion.pk])
		)
		self.assertFalse(Serie.objects.filter(pk=segunda_serie.pk).exists())
		self.assertEqual(
			list(sesion.series.values_list("numero_serie", flat=True)), [1]
		)

	def test_usuario_puede_eliminar_una_serie_y_las_series_se_reenumeran(self):
		usuario = get_user_model().objects.create_user(
			username="series@example.com",
			email="series@example.com",
			password="UnaClaveSegura123!",
		)
		otro_usuario = get_user_model().objects.create_user(
			username="otro-series@example.com",
			email="otro-series@example.com",
			password="UnaClaveSegura123!",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Torso")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=usuario, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Press banca", grupo_muscular="Pecho")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion, entrenamiento_ejercicio=entrada
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now(),
		)
		series = [
			Serie.objects.create(
				sesion_entrenamiento=sesion,
				usuario_entrenamiento_ejercicio=seleccion,
				numero_serie=numero,
				repeticiones=10 - numero,
				peso=Decimal("50.00") + numero,
			)
			for numero in range(1, 4)
		]

		otra_rutina = Entrenamiento.objects.create(
			nombre="Torso", rutina_origen=entrenamiento
		)
		otra_asignacion = UsuarioEntrenamiento.objects.create(
			usuario=otro_usuario, entrenamiento=otra_rutina
		)
		otra_entrada = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=otra_asignacion,
			entrenamiento_ejercicio=EntrenamientoEjercicio.objects.create(
				entrenamiento=otra_rutina, ejercicio=ejercicio, orden=1
			),
		)
		otra_sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=otra_asignacion, fecha=timezone.now()
		)
		serie_ajena = Serie.objects.create(
			sesion_entrenamiento=otra_sesion,
			usuario_entrenamiento_ejercicio=otra_entrada,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("60.00"),
		)
		self.client.force_login(usuario)

		respuesta = self.client.get(reverse("historial_sesiones"))
		self.assertContains(respuesta, "Press banca")
		self.assertContains(respuesta, "Serie 1")
		self.assertContains(respuesta, "Serie 2")
		self.assertContains(respuesta, "Serie 3")

		respuesta = self.client.post(
			reverse("eliminar_serie_sesion", args=[sesion.pk, series[1].pk])
		)
		self.assertRedirects(respuesta, reverse("editar_sesion", args=[sesion.pk]))
		self.assertEqual(
			list(sesion.series.order_by("numero_serie").values_list("numero_serie", flat=True)),
			[1, 2],
		)
		self.assertEqual(
			list(sesion.series.order_by("numero_serie").values_list("repeticiones", flat=True)),
			[9, 7],
		)

		respuesta = self.client.post(
			reverse("eliminar_serie_sesion", args=[sesion.pk, serie_ajena.pk])
		)
		self.assertRedirects(respuesta, reverse("editar_sesion", args=[sesion.pk]))
		self.assertTrue(Serie.objects.filter(pk=serie_ajena.pk).exists())

	def test_panel_admin_desasigna_rutina_sin_borrar_historial_y_permite_reasignar(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		usuario = get_user_model().objects.create_user(
			username="usuario",
			email="usuario@example.com",
			password="UnaClaveSegura123!",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina conservada")
		ejercicio = Ejercicio.objects.create(nombre="Remo", grupo_muscular="Espalda")
		EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		self.client.force_login(admin_user)
		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk]),
			{"action": "asignar_usuario", "usuario": usuario.pk},
		)
		self.assertRedirects(
			respuesta, reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk])
		)
		asignacion = UsuarioEntrenamiento.objects.get(usuario=usuario)
		seleccion = asignacion.ejercicios_elegidos.get()
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion, fecha=timezone.now(), notas="Historial intacto"
		)
		serie = Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=10,
			peso=Decimal("35.00"),
		)
		respuesta = self.client.post(
			reverse(
				"panel_admin:entrenamiento_usuario_desasignar",
				args=[asignacion.entrenamiento_id, asignacion.pk],
			)
		)
		self.assertRedirects(
			respuesta,
			reverse(
				"panel_admin:entrenamiento_detalle",
				args=[asignacion.entrenamiento_id],
			),
		)
		asignacion.refresh_from_db()
		self.assertFalse(asignacion.activa)
		self.assertTrue(SesionEntrenamiento.objects.filter(pk=sesion.pk).exists())
		self.assertTrue(Serie.objects.filter(pk=serie.pk).exists())

		self.client.force_login(usuario)
		respuesta = self.client.get(reverse("dashboard"))
		self.assertNotContains(respuesta, "Rutina conservada")

		self.client.force_login(admin_user)
		respuesta = self.client.post(
			reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk]),
			{"action": "asignar_usuario", "usuario": usuario.pk},
		)
		self.assertRedirects(
			respuesta, reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk])
		)
		asignacion.refresh_from_db()
		self.assertTrue(asignacion.activa)
		self.assertEqual(
			UsuarioEntrenamiento.objects.filter(
				usuario=usuario, entrenamiento__rutina_origen=entrenamiento
			).count(),
			1,
		)
		self.assertTrue(SesionEntrenamiento.objects.filter(pk=sesion.pk).exists())
		self.assertTrue(Serie.objects.filter(pk=serie.pk).exists())

	def test_panel_admin_edita_usuario_sin_perder_sus_rutinas(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		user = get_user_model().objects.create_user(
			username="usuario",
			email="usuario@example.com",
			password="UnaClaveSegura123!",
		)
		grupo = Group.objects.create(name="Gimnasio")
		user.groups.add(grupo)
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina vinculada")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=user, entrenamiento=entrenamiento
		)
		self.client.force_login(admin_user)

		respuesta = self.client.post(
			reverse("panel_admin:usuario_editar", args=[user.pk]),
			{
				"username": "usuario-editado",
				"email": "editado@example.com",
				"is_active": "on",
				"password1": "nQ7!xL4#vB9@zC2",
				"password2": "nQ7!xL4#vB9@zC2",
			},
		)

		self.assertRedirects(
			respuesta, reverse("panel_admin:usuario_editar", args=[user.pk])
		)
		user.refresh_from_db()
		self.assertEqual(user.username, "usuario-editado")
		self.assertTrue(user.check_password("nQ7!xL4#vB9@zC2"))
		self.assertTrue(user.groups.filter(pk=grupo.pk).exists())
		self.assertTrue(UsuarioEntrenamiento.objects.filter(pk=asignacion.pk, usuario=user).exists())


class PerfilUsuarioAdminMigrationTests(TransactionTestCase):
	def test_migracion_crea_copias_personales_y_conserva_las_series(self):
		migration_anterior = ("tracker", "0006_usuarioentrenamiento_activa")
		migracion_actual = (
			"tracker",
			"0007_entrenamiento_es_plantilla_entrenamiento_plantilla_and_more",
		)
		executor = MigrationExecutor(connection)
		executor.migrate([migration_anterior])
		apps_anteriores = executor.loader.project_state([migration_anterior]).apps
		User = get_user_model()
		usuario_uno = User.objects.create_user(
			username="migracion-uno", email="migracion-uno@example.com"
		)
		usuario_dos = User.objects.create_user(
			username="migracion-dos", email="migracion-dos@example.com"
		)
		EntrenamientoAntiguo = apps_anteriores.get_model("tracker", "Entrenamiento")
		EjercicioAntiguo = apps_anteriores.get_model("tracker", "Ejercicio")
		EntradaAntigua = apps_anteriores.get_model("tracker", "EntrenamientoEjercicio")
		AsignacionAntigua = apps_anteriores.get_model("tracker", "UsuarioEntrenamiento")
		SeleccionAntigua = apps_anteriores.get_model(
			"tracker", "UsuarioEntrenamientoEjercicio"
		)
		SesionAntigua = apps_anteriores.get_model("tracker", "SesionEntrenamiento")
		SerieAntigua = apps_anteriores.get_model("tracker", "Serie")
		rutina = EntrenamientoAntiguo.objects.create(nombre="Plantilla legada")
		ejercicio = EjercicioAntiguo.objects.create(
			nombre="Sentadilla migrada", grupo_muscular="Piernas"
		)
		entrada = EntradaAntigua.objects.create(
			entrenamiento=rutina, ejercicio=ejercicio, orden=1
		)
		asignaciones = [
			AsignacionAntigua.objects.create(usuario_id=usuario.pk, entrenamiento=rutina)
			for usuario in (usuario_uno, usuario_dos)
		]
		selecciones = [
			SeleccionAntigua.objects.create(
				usuario_entrenamiento=asignacion,
				entrenamiento_ejercicio=entrada,
			)
			for asignacion in asignaciones
		]
		sesion = SesionAntigua.objects.create(
			usuario_entrenamiento=asignaciones[0], fecha=timezone.now()
		)
		serie = SerieAntigua.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=selecciones[0],
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("70.00"),
		)

		try:
			executor = MigrationExecutor(connection)
			executor.migrate([migracion_actual])
			apps_actuales = executor.loader.project_state([migracion_actual]).apps
			EntrenamientoActual = apps_actuales.get_model("tracker", "Entrenamiento")
			AsignacionActual = apps_actuales.get_model("tracker", "UsuarioEntrenamiento")
			SeleccionActual = apps_actuales.get_model(
				"tracker", "UsuarioEntrenamientoEjercicio"
			)
			SerieActual = apps_actuales.get_model("tracker", "Serie")
			plantilla = EntrenamientoActual.objects.get(pk=rutina.pk)
			asignacion_uno = AsignacionActual.objects.get(pk=asignaciones[0].pk)
			asignacion_dos = AsignacionActual.objects.get(pk=asignaciones[1].pk)
			self.assertTrue(plantilla.es_plantilla)
			self.assertNotEqual(asignacion_uno.entrenamiento_id, rutina.pk)
			self.assertNotEqual(asignacion_dos.entrenamiento_id, rutina.pk)
			self.assertNotEqual(
				asignacion_uno.entrenamiento_id, asignacion_dos.entrenamiento_id
			)
			self.assertEqual(
				asignacion_uno.entrenamiento.plantilla_id,
				asignacion_dos.entrenamiento.plantilla_id,
			)
			self.assertEqual(
				SerieActual.objects.get(pk=serie.pk)
				.usuario_entrenamiento_ejercicio_id,
				SeleccionActual.objects.get(pk=selecciones[0].pk).pk,
			)
			self.assertEqual(
				SeleccionActual.objects.get(pk=selecciones[0].pk)
				.entrenamiento_ejercicio.entrenamiento_id,
				asignacion_uno.entrenamiento_id,
			)
		finally:
			executor = MigrationExecutor(connection)
			executor.migrate(executor.loader.graph.leaf_nodes())

	def test_user_edit_does_not_depend_on_group_join_table(self):
		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		user = get_user_model().objects.create_user(
			username="usuario",
			email="usuario@example.com",
			password="UnaClaveSegura123!",
		)
		group_through = get_user_model()._meta.get_field("groups").remote_field.through
		self.client.force_login(admin_user)
		self.client.raise_request_exception = False

		with connection.schema_editor() as schema_editor:
			schema_editor.delete_model(group_through)
		try:
			response = self.client.get(
				reverse("panel_admin:usuario_editar", args=[user.pk])
			)
		finally:
			with connection.schema_editor() as schema_editor:
				schema_editor.create_model(group_through)

		self.assertEqual(response.status_code, 200)

	def test_missing_profile_table_does_not_break_admin_and_migration_restores_it(self):
		from django.apps import apps

		admin_user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="UnaClaveSegura123!",
		)
		user = get_user_model().objects.create_user(
			username="usuario",
			email="usuario@example.com",
			password="UnaClaveSegura123!",
		)
		profile_model = apps.get_model("tracker", "PerfilUsuario")
		migration = __import__(
			"tracker.migrations.0005_ensure_perfilusuario_table",
			fromlist=["ensure_perfilusuario_table"],
		)
		self.client.force_login(admin_user)
		self.client.raise_request_exception = False
		change_url = reverse("panel_admin:usuario_editar", args=[user.pk])

		with connection.schema_editor() as schema_editor:
			schema_editor.delete_model(profile_model)

		response = self.client.get(change_url)
		self.assertEqual(response.status_code, 200)

		with connection.schema_editor() as schema_editor:
			migration.ensure_perfilusuario_table(apps, schema_editor)
			migration.ensure_perfilusuario_table(apps, schema_editor)

		response = self.client.get(change_url)

		self.assertEqual(response.status_code, 200)

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

	def test_registro_publico_esta_disponible(self):
		respuesta = self.client.get("/registro/")

		self.assertEqual(respuesta.status_code, 200)

	def test_usuario_puede_crear_entrenamiento_con_ejercicios(self):
		cuenta = get_user_model().objects.create_user(
			username="carlos@example.com",
			email="carlos@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = vincular_usuario_gimnasio(cuenta, "Carlos")
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

	def test_usuario_puede_crear_rutina_vacia_y_anadir_ejercicio_desde_catalogo(self):
		cuenta = get_user_model().objects.create_user(
			username="rutina-vacia@example.com",
			email="rutina-vacia@example.com",
			password="UnaClaveSegura123!",
		)
		self.client.force_login(cuenta)

		respuesta = self.client.post(
			reverse("crear_entrenamiento"),
			{"nombre": "Rutina progresiva", "descripcion": "La completaré después."},
		)

		self.assertRedirects(respuesta, reverse("dashboard"))
		asignacion = UsuarioEntrenamiento.objects.get(usuario=cuenta)
		self.assertEqual(asignacion.ejercicios_elegidos.count(), 0)
		otro_usuario = get_user_model().objects.create_user(
			username="asignado@example.com",
			email="asignado@example.com",
			password="UnaClaveSegura123!",
		)
		otra_rutina = Entrenamiento.objects.create(nombre="Rutina progresiva")
		otra_asignacion = UsuarioEntrenamiento.objects.create(
			usuario=otro_usuario, entrenamiento=otra_rutina
		)

		ejercicio = Ejercicio.objects.create(
			nombre="Press militar", grupo_muscular="Hombros", activo=True
		)
		respuesta = self.client.get(reverse("ejercicios"))
		self.assertContains(
			respuesta, "Despliega un ejercicio para añadirlo a una de tus rutinas personales."
		)
		self.assertContains(respuesta, f'value="{asignacion.pk}"')

		respuesta = self.client.post(
			reverse("ejercicio_anadir_a_rutina", args=[ejercicio.pk]),
			{"asignacion": asignacion.pk},
		)

		self.assertRedirects(respuesta, reverse("ejercicios"))
		self.assertEqual(asignacion.ejercicios_elegidos.count(), 1)
		entrada = EntrenamientoEjercicio.objects.get(
			entrenamiento=asignacion.entrenamiento, ejercicio=ejercicio
		)
		self.assertEqual(entrada.orden, 1)
		self.assertTrue(
			UsuarioEntrenamientoEjercicio.objects.filter(
				usuario_entrenamiento=asignacion,
				entrenamiento_ejercicio=entrada,
			).exists()
		)
		self.assertFalse(otra_asignacion.ejercicios_elegidos.exists())
		self.assertNotEqual(asignacion.entrenamiento_id, otra_asignacion.entrenamiento_id)

		respuesta = self.client.post(
			reverse("ejercicio_anadir_a_rutina", args=[ejercicio.pk]),
			{"asignacion": asignacion.pk},
			follow=True,
		)
		self.assertContains(respuesta, "ya está en Rutina progresiva.")
		self.assertEqual(asignacion.ejercicios_elegidos.count(), 1)

	def test_usuario_no_puede_anadir_ejercicio_a_rutina_ajena(self):
		usuario = get_user_model().objects.create_user(
			username="propietario@example.com",
			email="propietario@example.com",
			password="UnaClaveSegura123!",
		)
		otro_usuario = get_user_model().objects.create_user(
			username="ajeno@example.com",
			email="ajeno@example.com",
			password="UnaClaveSegura123!",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina privada")
		asignacion_ajena = UsuarioEntrenamiento.objects.create(
			usuario=otro_usuario, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(
			nombre="Elevación lateral", grupo_muscular="Hombros", activo=True
		)
		self.client.force_login(usuario)

		respuesta = self.client.post(
			reverse("ejercicio_anadir_a_rutina", args=[ejercicio.pk]),
			{"asignacion": asignacion_ajena.pk},
			follow=True,
		)

		self.assertContains(respuesta, "Selecciona una de tus rutinas activas")
		self.assertFalse(
			EntrenamientoEjercicio.objects.filter(
				entrenamiento=entrenamiento, ejercicio=ejercicio
			).exists()
		)

	def test_editar_rutina_muestra_marcados_los_ejercicios_asignados(self):
		cuenta = get_user_model().objects.create_user(
			username="rutina@example.com",
			email="rutina@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = vincular_usuario_gimnasio(cuenta, "Rutina")
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina existente")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=perfil, entrenamiento=entrenamiento
		)
		ejercicio_asignado = Ejercicio.objects.create(
			nombre="Press banca", grupo_muscular="Pecho"
		)
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio_asignado, orden=1
		)
		UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrada,
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
		vincular_usuario_gimnasio(cuenta, "Carlos")

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
		perfil = vincular_usuario_gimnasio(cuenta, "Inés")
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
		perfil = vincular_usuario_gimnasio(cuenta, "Eva")
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
		perfil = vincular_usuario_gimnasio(cuenta, "Eva")
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

	def test_usuario_puede_quitar_ejercicio_sin_borrar_su_historial_ni_afectar_a_otros(self):
		usuario = get_user_model().objects.create_user(
			username="rutina-personal@example.com",
			email="rutina-personal@example.com",
			password="UnaClaveSegura123!",
		)
		otro_usuario = get_user_model().objects.create_user(
			username="otra-rutina@example.com",
			email="otra-rutina@example.com",
			password="UnaClaveSegura123!",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Rutina propia")
		otra_rutina = Entrenamiento.objects.create(nombre="Rutina de otra persona")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=usuario, entrenamiento=entrenamiento
		)
		otra_asignacion = UsuarioEntrenamiento.objects.create(
			usuario=otro_usuario, entrenamiento=otra_rutina
		)
		ejercicio = Ejercicio.objects.create(nombre="Press inclinado", grupo_muscular="Pecho")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		otra_entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=otra_rutina, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion, entrenamiento_ejercicio=entrada
		)
		otra_seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=otra_asignacion,
			entrenamiento_ejercicio=otra_entrada,
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion, fecha=timezone.now()
		)
		serie = Serie.objects.create(
			sesion_entrenamiento=sesion,
			usuario_entrenamiento_ejercicio=seleccion,
			numero_serie=1,
			repeticiones=8,
			peso=Decimal("65.00"),
		)
		self.client.force_login(usuario)

		respuesta = self.client.post(
			reverse("editar_entrenamiento", args=[asignacion.pk]),
			{"nombre": "Rutina propia", "descripcion": ""},
		)

		self.assertRedirects(respuesta, reverse("dashboard"))
		seleccion.refresh_from_db()
		self.assertFalse(seleccion.activo)
		self.assertTrue(Serie.objects.filter(pk=serie.pk).exists())
		self.assertTrue(otra_seleccion.activo)
		self.assertTrue(
			UsuarioEntrenamientoEjercicio.objects.filter(pk=otra_seleccion.pk).exists()
		)
		respuesta = self.client.get(reverse("editar_sesion", args=[sesion.pk]))
		self.assertContains(respuesta, "historial conservado")
		self.assertNotContains(respuesta, "Editar ejercicio")
		respuesta = self.client.post(
			reverse("ejercicio_anadir_a_rutina", args=[ejercicio.pk]),
			{"asignacion": asignacion.pk},
		)
		self.assertRedirects(respuesta, reverse("ejercicios"))
		seleccion.refresh_from_db()
		self.assertTrue(seleccion.activo)
		self.assertTrue(Serie.objects.filter(pk=serie.pk).exists())

	def test_inicio_muestra_estadisticas_y_historial_de_sesiones(self):
		cuenta = get_user_model().objects.create_user(
			username="lucia@example.com", email="lucia@example.com", password="UnaClaveSegura123!"
		)
		perfil = vincular_usuario_gimnasio(cuenta, "Lucía")
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
		perfil = vincular_usuario_gimnasio(cuenta, "Marta")
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

	def test_editar_sesion_precarga_el_numero_de_series_y_sus_valores(self):
		cuenta = get_user_model().objects.create_user(
			username="lucia@example.com", email="lucia@example.com",
		)
		entrenamiento = Entrenamiento.objects.create(nombre="Pierna")
		asignacion = UsuarioEntrenamiento.objects.create(
			usuario=cuenta, entrenamiento=entrenamiento
		)
		ejercicio = Ejercicio.objects.create(nombre="Prensa", grupo_muscular="Piernas")
		entrada = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento, ejercicio=ejercicio, orden=1
		)
		seleccion = UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion, entrenamiento_ejercicio=entrada
		)
		sesion = SesionEntrenamiento.objects.create(
			usuario_entrenamiento=asignacion,
			fecha=timezone.now(),
			notas="Controlar el tempo",
		)
		series_guardadas = [
			(12, Decimal("40.50")),
			(10, Decimal("42.00")),
			(8, Decimal("44.25")),
		]
		for numero, (repeticiones, peso) in enumerate(series_guardadas, start=1):
			Serie.objects.create(
				sesion_entrenamiento=sesion,
				usuario_entrenamiento_ejercicio=seleccion,
				numero_serie=numero,
				repeticiones=repeticiones,
				peso=peso,
			)
		self.client.force_login(cuenta)

		url = reverse("editar_sesion", args=[sesion.pk])
		respuesta = self.client.get(url, {"ejercicio": seleccion.pk})

		self.assertEqual(respuesta.status_code, 200)
		form = respuesta.context["form"]
		self.assertContains(respuesta, '<h2>Editar ejercicio</h2>')
		self.assertContains(respuesta, 'id="exercise-form"')
		self.assertContains(respuesta, f"?ejercicio={seleccion.pk}#exercise-form")
		self.assertNotContains(respuesta, "Añadir o editar ejercicio")
		self.assertEqual(form["numero_series"].value(), 3)
		self.assertEqual(form["notas"].value(), "Controlar el tempo")
		for numero, (repeticiones, peso) in enumerate(series_guardadas, start=1):
			self.assertEqual(form[f"reps_{numero}"].value(), repeticiones)
			self.assertEqual(form[f"peso_{numero}"].value(), peso)

		respuesta = self.client.post(
			url,
			{
				"editar_ejercicio": seleccion.pk,
				"ejercicio": seleccion.pk,
				"numero_series": 3,
				"reps_1": 12,
				"peso_1": "40.50",
				"reps_2": 10,
				"peso_2": "42.00",
				"reps_3": 8,
				"peso_3": "44.25",
				"notas": "Controlar el tempo",
			},
		)

		self.assertRedirects(respuesta, url)
		sesion.refresh_from_db()
		self.assertEqual(sesion.notas, "Controlar el tempo")
		self.assertEqual(
			list(
				sesion.series.order_by("numero_serie").values_list(
					"repeticiones", "peso"
				)
			),
			[(repeticiones, peso) for repeticiones, peso in series_guardadas],
		)
