from django.db import transaction

from .models import (
	Entrenamiento,
	EntrenamientoEjercicio,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


@transaction.atomic
def purgar_rutina_eliminada_sin_sesiones(entrenamiento_id):
	entrenamiento = (
		Entrenamiento.objects.select_for_update()
		.filter(pk=entrenamiento_id, eliminada=True)
		.first()
	)
	if entrenamiento is None:
		return False
	if SesionEntrenamiento.objects.filter(
		usuario_entrenamiento__entrenamiento=entrenamiento
	).exists():
		return False
	if Serie.objects.filter(
		usuario_entrenamiento_ejercicio__usuario_entrenamiento__entrenamiento=entrenamiento
	).exists():
		return False

	UsuarioEntrenamientoEjercicio.objects.filter(
		usuario_entrenamiento__entrenamiento=entrenamiento
	).delete()
	UsuarioEntrenamiento.objects.filter(entrenamiento=entrenamiento).delete()
	EntrenamientoEjercicio.objects.filter(entrenamiento=entrenamiento).delete()
	entrenamiento.delete()
	return True


@transaction.atomic
def copiar_rutina_para_usuario(rutina, usuario, nombre=None):
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
		nombre=nombre or f"{rutina.nombre} (copia)",
		descripcion=rutina.descripcion,
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
