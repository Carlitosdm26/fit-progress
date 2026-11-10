from django.db import transaction

from .models import (
	Entrenamiento,
	EntrenamientoEjercicio,
	Serie,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


@transaction.atomic
def copiar_rutina_para_usuario(rutina, usuario):
	rutina_origen = rutina.rutina_origen or rutina
	asignacion_origen = UsuarioEntrenamiento.objects.filter(
		entrenamiento=rutina,
		activa=True,
	).first()
	ejercicios = rutina.ejercicios.all()
	if asignacion_origen is not None:
		ejercicios = ejercicios.filter(
			elecciones__usuario_entrenamiento=asignacion_origen,
			elecciones__activo=True,
		)

	entrenamiento = Entrenamiento.objects.create(
		nombre=rutina.nombre,
		descripcion=rutina.descripcion,
		rutina_origen=rutina_origen,
	)
	asignacion = UsuarioEntrenamiento.objects.create(
		usuario=usuario,
		entrenamiento=entrenamiento,
	)
	for entrada in ejercicios:
		entrada_personal = EntrenamientoEjercicio.objects.create(
			entrenamiento=entrenamiento,
			ejercicio=entrada.ejercicio,
			orden=entrada.orden,
		)
		UsuarioEntrenamientoEjercicio.objects.create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrada_personal,
		)
	return asignacion


@transaction.atomic
def eliminar_serie_y_reenumerar(serie):
	series_restantes = list(
		Serie.objects.filter(
			sesion_entrenamiento_id=serie.sesion_entrenamiento_id,
			usuario_entrenamiento_ejercicio_id=serie.usuario_entrenamiento_ejercicio_id,
		).exclude(pk=serie.pk).order_by("numero_serie")
	)
	serie.delete()
	if not series_restantes:
		return

	offset = max(item.numero_serie for item in series_restantes) + len(series_restantes)
	for item in series_restantes:
		item.numero_serie += offset
	Serie.objects.bulk_update(series_restantes, ["numero_serie"])

	for numero, item in enumerate(series_restantes, start=1):
		item.numero_serie = numero
	Serie.objects.bulk_update(series_restantes, ["numero_serie"])
