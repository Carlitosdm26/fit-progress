from django.db import transaction

from .models import Serie


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
