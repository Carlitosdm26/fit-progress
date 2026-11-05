from django.urls import path

from . import admin_views

app_name = "panel_admin"

urlpatterns = [
	path("", admin_views.panel_inicio, name="inicio"),
	path("usuarios/", admin_views.usuarios, name="usuarios"),
	path("usuarios/nuevo/", admin_views.usuario_nuevo, name="usuario_nuevo"),
	path("usuarios/<int:user_id>/", admin_views.usuario_editar, name="usuario_editar"),
	path("ejercicios/", admin_views.ejercicios, name="ejercicios"),
	path("ejercicios/nuevo/", admin_views.ejercicio_nuevo, name="ejercicio_nuevo"),
	path("ejercicios/<int:ejercicio_id>/", admin_views.ejercicio_editar, name="ejercicio_editar"),
	path("entrenamientos/", admin_views.entrenamientos, name="entrenamientos"),
	path("entrenamientos/nuevo/", admin_views.entrenamiento_nuevo, name="entrenamiento_nuevo"),
	path("entrenamientos/<int:entrenamiento_id>/", admin_views.entrenamiento_detalle, name="entrenamiento_detalle"),
	path("entrenamientos/<int:entrenamiento_id>/usuarios/<int:user_id>/desasignar/", admin_views.entrenamiento_usuario_desasignar, name="entrenamiento_usuario_desasignar"),
	path("entrenamientos/<int:entrenamiento_id>/ejercicios/<int:entrada_id>/", admin_views.entrenamiento_ejercicio_editar, name="entrenamiento_ejercicio_editar"),
	path("entrenamientos/<int:entrenamiento_id>/ejercicios/<int:entrada_id>/quitar/", admin_views.entrenamiento_ejercicio_eliminar, name="entrenamiento_ejercicio_eliminar"),
	path("sesiones/", admin_views.sesiones, name="sesiones"),
	path("sesiones/nueva/", admin_views.sesion_nueva, name="sesion_nueva"),
	path("sesiones/<int:sesion_id>/", admin_views.sesion_detalle, name="sesion_detalle"),
	path("series/<int:serie_id>/", admin_views.serie_editar, name="serie_editar"),
]