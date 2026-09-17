from datetime import datetime
from decimal import Decimal

from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
	Ejercicio,
	Entrenamiento,
	EntrenamientoEjercicio,
	Serie,
	SesionEntrenamiento,
	Usuario,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


class SeguimientoModelTests(TestCase):
	def setUp(self):
		self.usuario = Usuario.objects.create(nombre="Ana", email="ana@example.com")
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
	def test_no_existe_registro_publico(self):
		respuesta = self.client.get("/registro/")

		self.assertEqual(respuesta.status_code, 404)

	def test_usuario_puede_crear_entrenamiento_con_ejercicios(self):
		cuenta = get_user_model().objects.create_user(
			username="carlos@example.com",
			email="carlos@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = Usuario.objects.create(
			nombre="Carlos", email="carlos@example.com", cuenta=cuenta
		)
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

	def test_catalogo_requiere_login(self):
		respuesta = self.client.get(reverse("ejercicios"))

		self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('ejercicios')}")

	def test_usuario_puede_registrar_repeticiones_y_peso(self):
		cuenta = get_user_model().objects.create_user(
			username="ines@example.com",
			email="ines@example.com",
			password="UnaClaveSegura123!",
		)
		perfil = Usuario.objects.create(nombre="Inés", email="ines@example.com", cuenta=cuenta)
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
		perfil = Usuario.objects.create(nombre="Eva", email="eva@example.com", cuenta=cuenta)
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

	def test_usuario_puede_editar_rutina(self):
		cuenta = get_user_model().objects.create_user(
			username="eva@example.com", email="eva@example.com", password="UnaClaveSegura123!"
		)
		perfil = Usuario.objects.create(nombre="Eva", email="eva@example.com", cuenta=cuenta)
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
		perfil = Usuario.objects.create(nombre="Lucía", email="lucia@example.com", cuenta=cuenta)
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
		perfil = Usuario.objects.create(nombre="Marta", email="marta@example.com", cuenta=cuenta)
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
