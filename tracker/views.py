import logging
from collections import defaultdict
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.utils import timezone

from .forms import (
	AgregarEjercicioARutinaForm,
	EmailOrUsernameAuthenticationForm,
	EjercicioForm,
	EjercicioSesionForm,
	EntrenamientoForm,
	RegistroForm,
)
from .models import (
	Entrenamiento,
	EntrenamientoEjercicio,
	Ejercicio,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)
from .services import eliminar_serie_y_reenumerar

logger = logging.getLogger("tracker")


def get_client_ip(request):
	forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
	if forwarded_for:
		return forwarded_for.split(",")[0].strip()
	return request.META.get("REMOTE_ADDR", "unknown")


def perfil_actual(request):
	return request.user


def active_user_required(view_func):
	@wraps(view_func)
	def wrapped_view(request, *args, **kwargs):
		if not request.user.is_active:
			return render(request, "tracker/cuenta_inactiva.html", status=403)
		return view_func(request, *args, **kwargs)

	return wrapped_view


def login_view(request):
	client_ip = get_client_ip(request)
	redirect_to = request.POST.get("next") or request.GET.get("next")
	if not url_has_allowed_host_and_scheme(
		redirect_to,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		redirect_to = None
	if request.user.is_authenticated:
		logger.debug("Usuario ya autenticado, redirigiendo al inicio. user=%s ip=%s", request.user.username, client_ip)
		return redirect(redirect_to or "inicio")
	form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
	if request.method == "POST":
		logger.debug("Intento de login para username=%s ip=%s", request.POST.get("username"), client_ip)
	if request.method == "POST" and form.is_valid():
		user = form.get_user()
		login(request, user)
		logger.info("Usuario %s ha iniciado sesión.", user.username)
		logger.debug("Login correcto. user=%s email=%s ip=%s request_path=%s", user.username, user.email, client_ip, request.path)
		return redirect(redirect_to or "inicio")
	if request.method == "GET":
		logger.debug("Acceso a la página de login. ip=%s", client_ip)
	return render(request, "tracker/login.html", {"form": form})


def register_view(request):
	if request.user.is_authenticated:
		logger.debug("Usuario ya autenticado al intentar registrarse. user=%s", request.user.username)
		return redirect("inicio")
	form = RegistroForm(request.POST or None)
	if request.method == "POST":
		logger.debug("Intento de registro con username=%s email=%s", request.POST.get("username"), request.POST.get("email"))
	if request.method == "POST" and form.is_valid():
		user = form.save()
		logger.info("Usuario %s se ha registrado.", user.username)
		logger.debug("Registro completado. username=%s email=%s", user.username, user.email)
		auth_user = authenticate(
			request,
			username=user.username,
			password=form.cleaned_data["password1"],
		)
		if auth_user is not None:
			login(request, auth_user)
			logger.info("Usuario %s ha iniciado sesión tras el registro.", auth_user.username)
			logger.debug("Login tras registro correcto. user=%s", auth_user.username)
			return redirect("inicio")
		logger.warning("Registro completado pero no se pudo autenticar al usuario=%s", user.username)
		return redirect("login")
	return render(request, "tracker/register.html", {"form": form})


@login_required
def logout_view(request):
	if request.method == "POST":
		logout(request)
	return redirect("login")


@login_required
@active_user_required
def dashboard(request):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	asignaciones = UsuarioEntrenamiento.objects.select_related(
		"entrenamiento"
	).filter(usuario=perfil, activa=True, entrenamiento__eliminada=False)
	sesiones_qs = SesionEntrenamiento.objects.select_related(
		"usuario_entrenamiento__entrenamiento"
	).filter(usuario_entrenamiento__usuario=perfil).prefetch_related("series")
	ultimas_sesiones = sesiones_qs.order_by("-fecha")[:5]
	fecha_limite = timezone.now() - timedelta(days=30)
	dias_trabajados = sesiones_qs.values_list("fecha__date", flat=True).distinct().count()
	sesiones_ultimos_30_dias = sesiones_qs.filter(fecha__gte=fecha_limite).count()
	series_ultimos_30_dias = Serie.objects.filter(
		sesion_entrenamiento__usuario_entrenamiento__usuario=perfil,
		sesion_entrenamiento__fecha__gte=fecha_limite,
	).count()

	return render(
		request,
		"tracker/dashboard.html",
		{
			"asignaciones": asignaciones,
			"ultimas_sesiones": ultimas_sesiones,
			"dias_trabajados": dias_trabajados,
			"sesiones_ultimos_30_dias": sesiones_ultimos_30_dias,
			"series_ultimos_30_dias": series_ultimos_30_dias,
			"perfil": perfil,
		},
	)


@login_required
@active_user_required
def historial_sesiones(request):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	sesiones = SesionEntrenamiento.objects.select_related(
		"usuario_entrenamiento__entrenamiento"
	).filter(usuario_entrenamiento__usuario=perfil).prefetch_related(
		Prefetch(
			"series",
			queryset=Serie.objects.select_related(
				"usuario_entrenamiento_ejercicio__entrenamiento_ejercicio__ejercicio"
			).order_by(
				"usuario_entrenamiento_ejercicio__entrenamiento_ejercicio__orden",
				"numero_serie",
			),
		)
	).order_by("-fecha")
	historial = []
	por_dia = defaultdict(list)
	for sesion in sesiones:
		por_dia[sesion.fecha.date()].append(sesion)
	for dia, sesiones_dia in sorted(por_dia.items(), reverse=True):
		historial.append({"fecha": dia, "sesiones": sesiones_dia})
	return render(
		request,
		"tracker/historial.html",
		{"perfil": perfil, "historial": historial},
	)


@login_required
@active_user_required
def ejercicios(request):
	perfil = perfil_actual(request)
	form = EjercicioForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		ejercicio = form.save()
		messages.success(request, f"{ejercicio.nombre} se añadió al catálogo.")
		return redirect("ejercicios")
	asignaciones = list(
		UsuarioEntrenamiento.objects.filter(usuario=perfil, activa=True)
		.select_related("entrenamiento")
		.prefetch_related(
			"ejercicios_elegidos__entrenamiento_ejercicio"
		)
		.order_by("entrenamiento__nombre")
	)
	ejercicios = list(Ejercicio.objects.filter(activo=True))
	ejercicios_por_asignacion = {
		asignacion.pk: {
			seleccion.entrenamiento_ejercicio.ejercicio_id
			for seleccion in asignacion.ejercicios_elegidos.filter(activo=True)
		}
		for asignacion in asignaciones
	}
	for ejercicio in ejercicios:
		ejercicio.rutinas_disponibles = [
			asignacion
			for asignacion in asignaciones
			if ejercicio.pk not in ejercicios_por_asignacion[asignacion.pk]
		]
	return render(
		request,
		"tracker/ejercicios.html",
		{
			"ejercicios": ejercicios,
			"asignaciones": asignaciones,
			"form": form,
		},
	)


@login_required
@active_user_required
@require_POST
def ejercicio_anadir_a_rutina(request, ejercicio_id):
	perfil = perfil_actual(request)
	ejercicio = get_object_or_404(Ejercicio, pk=ejercicio_id, activo=True)
	form = AgregarEjercicioARutinaForm(perfil, request.POST)
	if not form.is_valid():
		messages.error(request, "Selecciona una de tus rutinas activas para añadir el ejercicio.")
		return redirect("ejercicios")
	asignacion = form.cleaned_data["asignacion"]
	with transaction.atomic():
		asignacion = UsuarioEntrenamiento.objects.select_for_update().filter(
			pk=asignacion.pk, usuario=perfil, activa=True
		).first()
		if asignacion is None:
			messages.error(request, "Esa rutina ya no está disponible.")
			return redirect("ejercicios")
		entrenamiento = Entrenamiento.objects.select_for_update().get(
			pk=asignacion.entrenamiento_id
		)
		entrada = EntrenamientoEjercicio.objects.filter(
			entrenamiento=entrenamiento, ejercicio=ejercicio
		).first()
		if entrada is None:
			ultimo_orden = entrenamiento.ejercicios.order_by("-orden").values_list(
				"orden", flat=True
			).first() or 0
			entrada = EntrenamientoEjercicio.objects.create(
				entrenamiento=entrenamiento,
				ejercicio=ejercicio,
				orden=ultimo_orden + 1,
			)
		seleccion, creada = UsuarioEntrenamientoEjercicio.objects.get_or_create(
			usuario_entrenamiento=asignacion,
			entrenamiento_ejercicio=entrada,
		)
		if not creada and not seleccion.activo:
			seleccion.activo = True
			seleccion.save(update_fields=["activo"])
			creada = True
	if creada:
		messages.success(request, f"{ejercicio.nombre} se añadió a {entrenamiento.nombre}.")
	else:
		messages.info(request, f"{ejercicio.nombre} ya está en {entrenamiento.nombre}.")
	return redirect("ejercicios")


@login_required
@active_user_required
def crear_entrenamiento(request):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	form = EntrenamientoForm(request.POST or None)
	ejercicios_seleccionados = {
		str(ejercicio_id) for ejercicio_id in (form["ejercicios"].value() or [])
	}
	grupos_musculares = list(
		Ejercicio.objects.filter(activo=True)
		.exclude(grupo_muscular="")
		.order_by("grupo_muscular")
		.values_list("grupo_muscular", flat=True)
		.distinct()
	)
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
		logger.info(
			"Usuario %s ha creado la rutina '%s' con %s ejercicios.",
			request.user.username,
			entrenamiento.nombre,
			form.cleaned_data["ejercicios"].count(),
		)
		logger.debug(
			"Rutina creada con detalle. user=%s perfil_id=%s rutina=%s ejercicios=%s",
			request.user.username,
			perfil.pk,
			entrenamiento.nombre,
			[ejercicio.nombre for ejercicio in form.cleaned_data["ejercicios"]],
		)
		messages.success(request, "Entrenamiento creado correctamente.")
		return redirect("dashboard")
	return render(
		request,
		"tracker/crear_entrenamiento.html",
		{
			"form": form,
			"grupos_musculares": grupos_musculares,
			"ejercicios_seleccionados": ejercicios_seleccionados,
		},
	)


@login_required
@active_user_required
def editar_entrenamiento(request, asignacion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	asignacion = UsuarioEntrenamiento.objects.select_related("entrenamiento").filter(
		pk=asignacion_id, usuario=perfil, activa=True
	).first()
	if asignacion is None:
		return redirect("dashboard")
	entrenamiento = asignacion.entrenamiento
	selecciones = list(
		asignacion.ejercicios_elegidos.select_related(
			"entrenamiento_ejercicio__ejercicio"
		)
	)
	seleccionadas_activas = [
		seleccion
		for seleccion in selecciones
		if seleccion.activo
	]
	seleccionados = [
		seleccion.entrenamiento_ejercicio.ejercicio_id
		for seleccion in seleccionadas_activas
	]
	form = EntrenamientoForm(
		request.POST or None,
		initial={
			"nombre": entrenamiento.nombre,
			"descripcion": entrenamiento.descripcion,
			"ejercicios": seleccionados,
		},
	)
	form.fields["ejercicios"].queryset = Ejercicio.objects.filter(
		Q(activo=True) | Q(pk__in=seleccionados)
	)
	ejercicios_seleccionados = {
		str(ejercicio_id) for ejercicio_id in (form["ejercicios"].value() or [])
	}
	if request.method == "POST" and form.is_valid():
		with transaction.atomic():
			entrenamiento.nombre = form.cleaned_data["nombre"]
			entrenamiento.descripcion = form.cleaned_data["descripcion"]
			entrenamiento.save(update_fields=["nombre", "descripcion"])
			selected_ids = {
				ejercicio.pk for ejercicio in form.cleaned_data["ejercicios"]
			}
			active_by_exercise = {
				seleccion.entrenamiento_ejercicio.ejercicio_id: seleccion
				for seleccion in seleccionadas_activas
			}
			for ejercicio_id, seleccion in active_by_exercise.items():
				if ejercicio_id in selected_ids:
					continue
				if seleccion.series.exists():
					seleccion.activo = False
					seleccion.save(update_fields=["activo"])
				else:
					entrada = seleccion.entrenamiento_ejercicio
					seleccion.delete()
					entrada.delete()
			inactive_by_exercise = {
				seleccion.entrenamiento_ejercicio.ejercicio_id: seleccion
				for seleccion in selecciones
				if not seleccion.activo
			}
			max_order = (
				entrenamiento.ejercicios.order_by("-orden")
				.values_list("orden", flat=True)
				.first()
				or 0
			)
			for ejercicio in form.cleaned_data["ejercicios"]:
				if ejercicio.pk in active_by_exercise:
					continue
				seleccion = inactive_by_exercise.get(ejercicio.pk)
				if seleccion is not None:
					seleccion.activo = True
					seleccion.save(update_fields=["activo"])
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
	grupos_musculares = list(
		Ejercicio.objects.filter(activo=True)
		.exclude(grupo_muscular="")
		.order_by("grupo_muscular")
		.values_list("grupo_muscular", flat=True)
		.distinct()
	)
	return render(
		request,
		"tracker/crear_entrenamiento.html",
		{
			"form": form,
			"asignacion": asignacion,
			"editando": True,
			"grupos_musculares": grupos_musculares,
			"ejercicios_seleccionados": ejercicios_seleccionados,
		},
	)


@login_required
@active_user_required
@require_POST
def eliminar_entrenamiento(request, asignacion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return redirect("login")
	with transaction.atomic():
		asignacion = UsuarioEntrenamiento.objects.select_for_update().filter(
			pk=asignacion_id, usuario=perfil, activa=True
		).first()
		if asignacion is None:
			return redirect("dashboard")
		entrenamiento = Entrenamiento.objects.select_for_update().get(
			pk=asignacion.entrenamiento_id
		)
		if entrenamiento.eliminada:
			return redirect("dashboard")
		entrenamiento.eliminada = True
		entrenamiento.save(update_fields=["eliminada"])
		UsuarioEntrenamiento.objects.filter(entrenamiento=entrenamiento).update(
			activa=False
		)
	messages.success(
		request,
		"La rutina se eliminó de tus rutinas. Tus sesiones e historial se conservaron.",
	)
	return redirect("dashboard")


@login_required
@active_user_required
def registrar_sesion(request, asignacion_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return render(request, "tracker/sin_perfil.html")
	asignacion = UsuarioEntrenamiento.objects.filter(
		pk=asignacion_id, usuario=perfil, activa=True
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
		logger.info(
			"Usuario %s ha registrado una sesión para la rutina '%s'.",
			request.user.username,
			asignacion.entrenamiento.nombre,
		)
		logger.debug(
			"Sesión registrada. user=%s rutina=%s ejercicio=%s series=%s notas=%s",
			request.user.username,
			asignacion.entrenamiento.nombre,
			form.cleaned_data["ejercicio"],
			len(form.series_data),
			form.cleaned_data.get("notas"),
		)
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
@active_user_required
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
			guardados.append(
				{
					"ejercicio": seleccion.entrenamiento_ejercicio.ejercicio,
					"seleccion": seleccion,
					"series": series,
					"editable": seleccion.activo,
				}
			)
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
@active_user_required
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
@active_user_required
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


@login_required
@active_user_required
@require_POST
def eliminar_serie_sesion(request, sesion_id, serie_id):
	perfil = perfil_actual(request)
	if perfil is None:
		return redirect("login")
	sesion = SesionEntrenamiento.objects.filter(
		pk=sesion_id, usuario_entrenamiento__usuario=perfil
	).first()
	if sesion is None:
		messages.error(request, "No se encontró esa sesión.")
		return redirect("dashboard")
	serie = Serie.objects.filter(pk=serie_id, sesion_entrenamiento=sesion).first()
	if serie is not None:
		ejercicio = serie.usuario_entrenamiento_ejercicio.entrenamiento_ejercicio.ejercicio.nombre
		eliminar_serie_y_reenumerar(serie)
		messages.success(request, f"Serie eliminada de {ejercicio}.")
	else:
		messages.error(request, "No se encontró esa serie en la sesión.")
	return redirect("editar_sesion", sesion_id=sesion.pk)


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
