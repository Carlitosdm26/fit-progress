from django.urls import path

from . import admin_views

app_name = "panel_admin"

urlpatterns = [
	path("", admin_views.panel_inicio, name="inicio"),
	path("usuarios/", admin_views.usuarios, name="usuarios"),
	path("usuarios/nuevo/", admin_views.usuario_nuevo, name="usuario_nuevo"),
	path("usuarios/<int:user_id>/", admin_views.usuario_editar, name="usuario_editar"),
]