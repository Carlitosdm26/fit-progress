from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from .forms import EjercicioSesionForm, EntrenamientoForm
from .models import (
	Entrenamiento,
	EntrenamientoEjercicio,
	Ejercicio,
	Serie,
	SesionEntrenamiento,
	Usuario,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)


def perfil_actual(request):
	try:
		return request.user.perfil_gimnasio
	except Usuario.DoesNotExist:
		return None


def login_view(request):
	if request.user.is_authenticated:
		return redirect("dashboard")
	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == "POST" and form.is_valid():
		login(request, form.get_user())
		return redirect("dashboard")
	return render(request, "tracker/login.html", {"form": form})


@login_required
def logout_view(request):
	if request.method == "POST":
		logout(request)
	return redirect("login")


@login_required
def dashboard(request):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	asignaciones = UsuarioEntrenamiento.objects.select_related(
		"entrenamiento"
	).filter(usuario=perfil)
	sesiones = SesionEntrenamiento.objects.select_related(
		"usuario_entrenamiento__entrenamiento"
	).filter(usuario_entrenamiento__usuario=perfil).prefetch_related("series")[:8]

	return render(
		request,
		"tracker/dashboard.html",
		{
			"asignaciones": asignaciones,
			"sesiones": sesiones,
			"series_registradas": Serie.objects.filter(
				sesion_entrenamiento__usuario_entrenamiento__usuario=perfil
			).count(),
			"perfil": perfil,
		},
	)


@login_required
def ejercicios(request):
	return render(
		request,
		"tracker/ejercicios.html",
		{"ejercicios": Ejercicio.objects.filter(activo=True)},
	)


@login_required
def crear_entrenamiento(request):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	form = EntrenamientoForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		with transaction.atomic():
			entrenamiento = Entrenamiento.objects.create(
				nombre=form.cleaned_data["nombre"],
				descripcion=form.cleaned_data["descripcion"],
			)
			asignacion = UsuarioEntrenamiento.objects.create(
				usuario=perfil, entrenamiento=entrenamiento
			)
			for orden, ejercicio in enumerate(form.cleaned_data["ejercicios"], start=1):
				entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
					entrenamiento=entrenamiento, ejercicio=ejercicio, orden=orden
				)
				UsuarioEntrenamientoEjercicio.objects.create(
					usuario_entrenamiento=asignacion,
					entrenamiento_ejercicio=entrenamiento_ejercicio,
				)
		messages.success(request, "Entrenamiento creado correctamente.")
		return redirect("dashboard")
	return render(request, "tracker/crear_entrenamiento.html", {"form": form})


@login_required
def editar_entrenamiento(request, asignacion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	asignacion = UsuarioEntrenamiento.objects.select_related("entrenamiento").filter(
		pk=asignacion_id, usuario=perfil
	).first()
	if asignacion is None:
		return redirect("dashboard")
	entrenamiento = asignacion.entrenamiento
	seleccionados = entrenamiento.ejercicios.values_list("ejercicio_id", flat=True)
	form = EntrenamientoForm(
		request.POST or None,
		initial={
			"nombre": entrenamiento.nombre,
			"descripcion": entrenamiento.descripcion,
			"ejercicios": seleccionados,
		},
	)
	if request.method == "POST" and form.is_valid():
		with transaction.atomic():
			entrenamiento.nombre = form.cleaned_data["nombre"]
			entrenamiento.descripcion = form.cleaned_data["descripcion"]
			entrenamiento.save(update_fields=["nombre", "descripcion"])
			existing_ids = set(seleccionados)
			max_order = entrenamiento.ejercicios.count()
			for ejercicio in form.cleaned_data["ejercicios"]:
				if ejercicio.pk in existing_ids:
					continue
				max_order += 1
				entrenamiento_ejercicio = EntrenamientoEjercicio.objects.create(
					entrenamiento=entrenamiento, ejercicio=ejercicio, orden=max_order
				)
				UsuarioEntrenamientoEjercicio.objects.create(
					usuario_entrenamiento=asignacion,
					entrenamiento_ejercicio=entrenamiento_ejercicio,
				)
		messages.success(request, "Rutina actualizada correctamente.")
		return redirect("dashboard")
	return render(
		request,
		"tracker/crear_entrenamiento.html",
		{"form": form, "asignacion": asignacion, "editando": True},
	)


@login_required
@require_POST
def eliminar_entrenamiento(request, asignacion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return redirect("login")
	asignacion = UsuarioEntrenamiento.objects.select_related("entrenamiento").filter(
		pk=asignacion_id, usuario=perfil
	).first()
	if asignacion is None:
		return redirect("dashboard")
	entrenamiento = asignacion.entrenamiento
	with transaction.atomic():
		SesionEntrenamiento.objects.filter(usuario_entrenamiento=asignacion).delete()
		asignacion.delete()
		if not entrenamiento.usuarios.exists():
			entrenamiento.delete()
	messages.success(request, "Rutina eliminada correctamente.")
	return redirect("dashboard")


@login_required
def registrar_sesion(request, asignacion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	asignacion = UsuarioEntrenamiento.objects.filter(
		pk=asignacion_id, usuario=perfil
	).first()
	if asignacion is None:
		return redirect("dashboard")
	form = EjercicioSesionForm(asignacion, data=request.POST or None)
	if request.method == "POST" and form.is_valid():
		with transaction.atomic():
			sesion = SesionEntrenamiento.objects.create(
				usuario_entrenamiento=asignacion,
				fecha=timezone.now(),
				notas=form.cleaned_data["notas"],
			)
			guardar_series(sesion, form)
		messages.success(request, "Sesión registrada correctamente.")
		return redirect("editar_sesion", sesion_id=sesion.pk)
	return render(
		request,
		"tracker/registrar_sesion.html",
		{
			"form": form,
			"asignacion": asignacion,
			"puede_anadir": form.fields["ejercicio"].queryset.exists(),
		},
	)


@login_required
def editar_sesion(request, sesion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	sesion = SesionEntrenamiento.objects.select_related(
		"usuario_entrenamiento__entrenamiento"
	).prefetch_related("series").filter(
		pk=sesion_id, usuario_entrenamiento__usuario=perfil
	).first()
	if sesion is None:
		return redirect("dashboard")
	asignacion = sesion.usuario_entrenamiento
	editar_seleccion_id = request.POST.get("editar_ejercicio") or request.GET.get("ejercicio")
	form = EjercicioSesionForm(
		asignacion,
		sesion=sesion,
		editar_seleccion_id=editar_seleccion_id,
		data=request.POST or None,
	)
	guardados = []
	for seleccion in asignacion.ejercicios_elegidos.select_related(
		"entrenamiento_ejercicio__ejercicio"
	):
		series = list(
			sesion.series.filter(usuario_entrenamiento_ejercicio=seleccion).order_by("numero_serie")
		)
		if series:
			guardados.append({"ejercicio": seleccion.entrenamiento_ejercicio.ejercicio, "seleccion": seleccion, "series": series})
	if request.method == "POST" and form.is_valid():
		with transaction.atomic():
			sesion.notas = form.cleaned_data["notas"]
			sesion.save(update_fields=["notas"])
			seleccion = form.cleaned_data["ejercicio"]
			sesion.series.filter(usuario_entrenamiento_ejercicio=seleccion).delete()
			guardar_series(sesion, form)
		messages.success(request, "Ejercicio guardado en la sesión.")
		return redirect("editar_sesion", sesion_id=sesion.pk)
	return render(
		request,
		"tracker/registrar_sesion.html",
		{
			"form": form,
			"asignacion": asignacion,
			"editando": True,
			"guardados": guardados,
			"sesion": sesion,
			"editando_ejercicio": editar_seleccion_id,
			"puede_anadir": form.fields["ejercicio"].queryset.exists(),
		},
	)


@login_required
@require_POST
def eliminar_sesion(request, sesion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return redirect("login")
	sesion = SesionEntrenamiento.objects.filter(
		pk=sesion_id, usuario_entrenamiento__usuario=perfil
	).first()
	if sesion is not None:
		sesion.delete()
		messages.success(request, "Sesión eliminada correctamente.")
	return redirect("dashboard")


@login_required
@require_POST
def eliminar_ejercicio_sesion(request, sesion_id, seleccion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return redirect("login")
	deleted, _ = Serie.objects.filter(
		sesion_entrenamiento_id=sesion_id,
		sesion_entrenamiento__usuario_entrenamiento__usuario=perfil,
		usuario_entrenamiento_ejercicio_id=seleccion_id,
	).delete()
	if deleted:
		messages.success(request, "Ejercicio eliminado de la sesión.")
	return redirect("editar_sesion", sesion_id=sesion_id)


def guardar_series(sesion, form):
	seleccion = form.cleaned_data["ejercicio"]
	Serie.objects.bulk_create(
		[
			Serie(
				sesion_entrenamiento=sesion,
				usuario_entrenamiento_ejercicio=seleccion,
				numero_serie=serie["numero_serie"],
				repeticiones=serie["repeticiones"],
				peso=serie["peso"],
			)
			for serie in form.series_data
		]
	)

# Create your views here.
