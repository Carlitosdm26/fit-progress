from django.core.management.base import BaseCommand
from django.db import transaction

from tracker.models import Ejercicio


EJERCICIOS = (
	{
		"nombre": "Prensa de piernas",
		"grupo_muscular": "Cuádriceps",
		"equipamiento": "Máquina de prensa",
		"descripcion": "3 series de 10 repeticiones; aumenta el peso en cada serie.",
	},
	{
		"nombre": "Sentadillas libres",
		"grupo_muscular": "Cuádriceps",
		"equipamiento": "Barra",
		"descripcion": "3 series de 10 repeticiones; aumenta el peso en cada serie.",
	},
	{
		"nombre": "Zancadas",
		"grupo_muscular": "Cuádriceps",
		"equipamiento": "Mancuernas",
		"descripcion": "3 series de 10 repeticiones por pierna con un peso sostenible.",
	},
	{
		"nombre": "Sillón de cuádriceps",
		"grupo_muscular": "Cuádriceps",
		"equipamiento": "Máquina de extensión de piernas",
		"descripcion": "3 series de 10 repeticiones y 1 repetición adicional al fallo.",
	},
	{
		"nombre": "Plancha frontal",
		"grupo_muscular": "Core",
		"equipamiento": "Peso corporal",
		"descripcion": "3 series de 45 segundos.",
	},
	{
		"nombre": "Russian twist con peso",
		"grupo_muscular": "Core",
		"equipamiento": "Disco o mancuerna",
		"descripcion": "3 series de 10 repeticiones por lado con un peso sostenible.",
	},
)


class Command(BaseCommand):
	help = "Añade al catálogo los ejercicios de la rutina de miércoles, sin duplicarlos."

	@transaction.atomic
	def handle(self, *args, **options):
		creados = 0
		for datos in EJERCICIOS:
			_, creado = Ejercicio.objects.get_or_create(
				nombre__iexact=datos["nombre"], defaults=datos
			)
			creados += int(creado)

		self.stdout.write(
			self.style.SUCCESS(
				f"{creados} ejercicios añadidos; {len(EJERCICIOS) - creados} ya existían."
			)
		)