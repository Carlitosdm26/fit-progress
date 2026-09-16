from django.contrib import admin

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


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
	list_display = ("nombre", "email", "cuenta", "activo", "fecha_registro")
	list_filter = ("activo",)
	search_fields = ("nombre", "email")
	autocomplete_fields = ("cuenta",)


@admin.register(Entrenamiento)
class EntrenamientoAdmin(admin.ModelAdmin):
	list_display = ("nombre", "fecha_creacion")
	search_fields = ("nombre", "descripcion")


@admin.register(Ejercicio)
class EjercicioAdmin(admin.ModelAdmin):
	list_display = ("nombre", "grupo_muscular", "equipamiento", "activo")
	list_filter = ("grupo_muscular", "activo")
	search_fields = ("nombre", "grupo_muscular")


admin.site.register(
	[
		UsuarioEntrenamiento,
		EntrenamientoEjercicio,
		UsuarioEntrenamientoEjercicio,
		SesionEntrenamiento,
		Serie,
	]
)
