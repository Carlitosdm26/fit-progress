from django.urls import path

from .views import (
    crear_entrenamiento,
    dashboard,
    editar_entrenamiento,
    editar_sesion,
    ejercicios,
    eliminar_ejercicio_sesion,
    eliminar_entrenamiento,
    eliminar_sesion,
    historial_sesiones,
    login_view,
    logout_view,
    registrar_sesion,
)

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("inicio/", dashboard, name="inicio"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("ejercicios/", ejercicios, name="ejercicios"),
    path("historial/", historial_sesiones, name="historial_sesiones"),
    path("entrenamientos/nuevo/", crear_entrenamiento, name="crear_entrenamiento"),
    path("entrenamientos/<int:asignacion_id>/editar/", editar_entrenamiento, name="editar_entrenamiento"),
    path("entrenamientos/<int:asignacion_id>/eliminar/", eliminar_entrenamiento, name="eliminar_entrenamiento"),
    path("sesiones/nueva/<int:asignacion_id>/", registrar_sesion, name="registrar_sesion"),
    path("sesiones/<int:sesion_id>/editar/", editar_sesion, name="editar_sesion"),
    path("sesiones/<int:sesion_id>/eliminar/", eliminar_sesion, name="eliminar_sesion"),
    path("sesiones/<int:sesion_id>/ejercicios/<int:seleccion_id>/eliminar/", eliminar_ejercicio_sesion, name="eliminar_ejercicio_sesion"),
]