from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import (
	DatoArchivado,
	Ejercicio,
	Entrenamiento,
	EntrenamientoEjercicio,
	PerfilUsuario,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


class PerfilUsuarioInline(admin.StackedInline):
	model = PerfilUsuario
	fields = ("descripcion",)
	can_delete = False
	max_num = 1

	def get_extra(self, request, obj=None, **kwargs):
		return 1 if obj is None or not hasattr(obj, "perfil_admin") else 0


class UsuarioCreationForm(UserCreationForm):
	class Meta(UserCreationForm.Meta):
		model = get_user_model()
		fields = ("username", "email")


class UsuarioChangeForm(UserChangeForm):
	class Meta(UserChangeForm.Meta):
		model = get_user_model()
		fields = "__all__"


class UsuarioAdmin(UserAdmin):
	form = UsuarioChangeForm
	add_form = UsuarioCreationForm
	list_display = ("username", "email", "is_active", "is_staff")
	search_fields = ("username", "email")
	ordering = ("username",)
	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": ("username", "email", "password1", "password2"),
			},
		),
	)
	fieldsets = (
		(None, {"fields": ("username", "password")}),
		(_("Personal info"), {"fields": ("email",)}),
		(
			_("Permissions"),
			{"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
		),
		(_("Important dates"), {"fields": ("last_login", "date_joined")}),
	)
	inlines = (PerfilUsuarioInline,)


admin.site.register(get_user_model(), UsuarioAdmin)


@admin.register(DatoArchivado)
class DatoArchivadoAdmin(admin.ModelAdmin):
	list_display = ("modelo", "registro_id", "campo")
	search_fields = ("modelo", "campo", "valor")
	readonly_fields = ("modelo", "registro_id", "campo", "valor")

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False


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
