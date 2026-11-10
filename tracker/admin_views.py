from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Min, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import (
	AdminAsignacionForm,
	AdminEjercicioForm,
	AdminEntrenamientoEjercicioForm,
	AdminEntrenamientoForm,
	AdminSerieForm,
	AdminSesionForm,
	AdminUsuarioCreationForm,
	AdminUsuarioUpdateForm,
)
from .models import (
	Ejercicio,
	Entrenamiento,
	EntrenamientoEjercicio,
	Serie,
	SesionEntrenamiento,
	UsuarioEntrenamiento,
	UsuarioEntrenamientoEjercicio,
)
from .services import copiar_rutina_para_usuario, eliminar_serie_y_reenumerar


def staff_required(view_func):
	@wraps(view_func)
	def wrapped_view(request, *args, **kwargs):
		if not request.user.is_authenticated:
			return redirect_to_login(request.get_full_path(), login_url=reverse("login"))
		if not request.user.is_active or not request.user.is_staff:
			return redirect("inicio")
		return view_func(request, *args, **kwargs)

	return wrapped_view


@staff_required
def panel_inicio(request):
	User = get_user_model()
	return render(
		request,
		"tracker/admin/dashboard.html",
		{
			"total_usuarios": User.objects.count(),
			"usuarios_activos": User.objects.filter(is_active=True).count(),
			"ejercicios": Ejercicio.objects.count(),
			"entrenamientos": Entrenamiento.objects.count(),
			"sesiones": SesionEntrenamiento.objects.count(),
			"ultimos_usuarios": User.objects.order_by("-date_joined")[:8],
		},
	)


@staff_required
def usuarios(request):
	User = get_user_model()
	query = request.GET.get("q", "").strip()
	estado = request.GET.get("estado", "")
	queryset = User.objects.all().order_by("username")
	if query:
		queryset = queryset.filter(Q(username__icontains=query) | Q(email__icontains=query))
	if estado == "activos":
		queryset = queryset.filter(is_active=True)
	elif estado == "inactivos":
		queryset = queryset.filter(is_active=False)
	page_obj = Paginator(queryset, 25).get_page(request.GET.get("page"))
	return render(
		request,
		"tracker/admin/usuarios.html",
		{"page_obj": page_obj, "query": query, "estado": estado},
	)


@staff_required
@require_http_methods(["GET", "POST"])
def usuario_nuevo(request):
	form = AdminUsuarioCreationForm(request.POST or None, actor=request.user)
	if request.method == "POST" and form.is_valid():
		usuario = form.save()
		messages.success(request, f"La cuenta {usuario.username} se creó correctamente.")
		return redirect("panel_admin:usuario_detalle", user_id=usuario.pk)
	return render(request, "tracker/admin/usuario_form.html", {"form": form, "nuevo": True})


def _usuario_actividad_context(usuario):
	return {
		"usuario": usuario,
		"rutinas_usuario": UsuarioEntrenamiento.objects.filter(usuario=usuario)
		.select_related("entrenamiento")
		.annotate(sesiones_count=Count("sesiones", distinct=True)),
		"sesiones_usuario": SesionEntrenamiento.objects.filter(
			usuario_entrenamiento__usuario=usuario
		)
		.select_related("usuario_entrenamiento__entrenamiento")
		.annotate(series_count=Count("series"))
		.order_by("-fecha")[:10],
	}


@staff_required
def usuario_detalle(request, user_id):
	usuario = get_object_or_404(get_user_model(), pk=user_id)
	return render(
		request,
		"tracker/admin/usuario_detalle.html",
		_usuario_actividad_context(usuario),
	)


@staff_required
@require_http_methods(["GET", "POST"])
def usuario_editar(request, user_id):
	User = get_user_model()
	usuario = get_object_or_404(User, pk=user_id)
	if usuario.is_superuser and not request.user.is_superuser:
		return HttpResponseForbidden("Solo un superusuario puede editar esta cuenta.")
	form = AdminUsuarioUpdateForm(request.POST or None, instance=usuario, actor=request.user)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, f"La cuenta {usuario.username} se actualizó correctamente.")
		return redirect("panel_admin:usuario_editar", user_id=usuario.pk)
	return render(
		request,
		"tracker/admin/usuario_form.html",
		{
			"form": form,
			"nuevo": False,
			**_usuario_actividad_context(usuario),
		},
	)


@staff_required
def ejercicios(request):
	query = request.GET.get("q", "").strip()
	queryset = Ejercicio.objects.annotate(
		rutinas_count=Count("entrenamientos", distinct=True)
	).order_by("nombre")
	if query:
		queryset = queryset.filter(
			Q(nombre__icontains=query)
			| Q(grupo_muscular__icontains=query)
			| Q(equipamiento__icontains=query)
		)
	return render(
		request,
		"tracker/admin/ejercicios.html",
		{"page_obj": Paginator(queryset, 30).get_page(request.GET.get("page")), "query": query},
	)


@staff_required
@require_http_methods(["GET", "POST"])
def ejercicio_nuevo(request):
	form = AdminEjercicioForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		ejercicio = form.save()
		messages.success(request, f"El ejercicio {ejercicio.nombre} se creó.")
		return redirect("panel_admin:ejercicios")
	return render(request, "tracker/admin/entidad_form.html", {"form": form, "titulo": "Nuevo ejercicio", "volver": reverse("panel_admin:ejercicios")})


@staff_required
@require_http_methods(["GET", "POST"])
def ejercicio_editar(request, ejercicio_id):
	ejercicio = get_object_or_404(Ejercicio, pk=ejercicio_id)
	form = AdminEjercicioForm(request.POST or None, instance=ejercicio)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, f"El ejercicio {ejercicio.nombre} se actualizó.")
		return redirect("panel_admin:ejercicios")
	return render(
		request,
		"tracker/admin/entidad_form.html",
		{"form": form, "titulo": f"Editar {ejercicio.nombre}", "volver": reverse("panel_admin:ejercicios")},
	)


@staff_required
def entrenamientos(request):
	query = request.GET.get("q", "").strip()
	queryset = Entrenamiento.objects.annotate(
		usuario_nombre=Min(
			"usuarios__usuario__username",
			filter=Q(usuarios__activa=True),
		),
		ejercicios_count=Count("ejercicios", distinct=True),
	).order_by("nombre", "pk")
	if query:
		queryset = queryset.filter(Q(nombre__icontains=query) | Q(descripcion__icontains=query))
	return render(
		request,
		"tracker/admin/entrenamientos.html",
		{"page_obj": Paginator(queryset, 30).get_page(request.GET.get("page")), "query": query},
	)


@staff_required
@require_http_methods(["GET", "POST"])
def entrenamiento_nuevo(request):
	form = AdminEntrenamientoForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		entrenamiento = form.save()
		messages.success(request, f"La rutina {entrenamiento.nombre} se creó.")
		return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)
	return render(
		request,
		"tracker/admin/entidad_form.html",
		{"form": form, "titulo": "Nueva rutina", "volver": reverse("panel_admin:entrenamientos")},
	)


@staff_required
@require_http_methods(["POST"])
def entrenamiento_eliminar(request, entrenamiento_id):
	entrenamiento = get_object_or_404(Entrenamiento, pk=entrenamiento_id)
	try:
		with transaction.atomic():
			Entrenamiento.objects.filter(rutina_origen=entrenamiento).update(
				rutina_origen_id=entrenamiento.rutina_origen_id
			)
			for asignacion in UsuarioEntrenamiento.objects.filter(
				entrenamiento=entrenamiento
			):
				SesionEntrenamiento.objects.filter(
					usuario_entrenamiento=asignacion
				).delete()
				UsuarioEntrenamientoEjercicio.objects.filter(
					usuario_entrenamiento=asignacion
				).delete()
				asignacion.delete()
			EntrenamientoEjercicio.objects.filter(entrenamiento=entrenamiento).delete()
			nombre = entrenamiento.nombre
			entrenamiento.delete()
	except ProtectedError:
		messages.error(
			request,
			"No se pudo eliminar la rutina porque algunos de sus ejercicios "
			"siguen vinculados a registros de otras rutinas.",
		)
	else:
		messages.success(
			request,
			f"Se eliminó la rutina {nombre} junto con sus sesiones e historial. "
			"Las copias de otros usuarios se conservaron.",
		)
	return redirect("panel_admin:entrenamientos")


@staff_required
@require_http_methods(["GET", "POST"])
def entrenamiento_detalle(request, entrenamiento_id):
	entrenamiento = get_object_or_404(Entrenamiento, pk=entrenamiento_id)
	action = request.POST.get("action") if request.method == "POST" else None
	form = AdminEntrenamientoForm(
		request.POST if action == "guardar_rutina" else None, instance=entrenamiento
	)
	asignacion_form = AdminAsignacionForm(
		request.POST if action == "asignar_usuario" else None, entrenamiento=entrenamiento
	)
	ejercicio_form = AdminEntrenamientoEjercicioForm(
		request.POST if action == "anadir_ejercicio" else None, entrenamiento=entrenamiento
	)
	if action == "guardar_rutina" and form.is_valid():
		form.save()
		messages.success(request, "La rutina se actualizó.")
		return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)
	if action == "asignar_usuario" and asignacion_form.is_valid():
		try:
			with transaction.atomic():
				usuario = asignacion_form.cleaned_data["usuario"]
				rutina_origen = entrenamiento.rutina_origen or entrenamiento
				rutinas_relacionadas = Entrenamiento.objects.filter(
					Q(pk=rutina_origen.pk) | Q(rutina_origen=rutina_origen)
				)
				asignacion = UsuarioEntrenamiento.objects.filter(
					usuario=usuario,
					entrenamiento__in=rutinas_relacionadas,
				).select_related("entrenamiento").order_by("-activa").first()
				creada = asignacion is None
				if creada:
					asignacion = copiar_rutina_para_usuario(entrenamiento, usuario)
				reactivada = not creada and not asignacion.activa
				if reactivada:
					asignacion.activa = True
					asignacion.save(update_fields=["activa"])
			if not creada and not reactivada:
				messages.error(request, "Este usuario ya tiene su propia copia de esta rutina.")
				return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)
		except IntegrityError:
			messages.error(request, "No se pudo crear otra copia para este usuario.")
		else:
			messages.success(
				request,
				f"Rutina {'copiada y asignada' if creada else 'reactivada'} "
				f"para {asignacion.usuario.username}.",
			)
			return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)
	if action == "anadir_ejercicio" and ejercicio_form.is_valid():
		try:
			with transaction.atomic():
				entrada = ejercicio_form.save(commit=False)
				entrada.entrenamiento = entrenamiento
				entrada.save()
				for asignacion in UsuarioEntrenamiento.objects.filter(
					entrenamiento=entrenamiento, activa=True
				):
					UsuarioEntrenamientoEjercicio.objects.create(
						usuario_entrenamiento=asignacion,
						entrenamiento_ejercicio=entrada,
					)
		except IntegrityError:
			messages.error(request, "No se pudo añadir: comprueba que el ejercicio y el orden no estén repetidos.")
		else:
			messages.success(
				request,
				"Ejercicio añadido a la rutina.",
			)
			return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)
	asignaciones = UsuarioEntrenamiento.objects.filter(
		entrenamiento=entrenamiento,
		activa=True,
	)
	asignacion = asignaciones.select_related("usuario").annotate(
		sesiones_count=Count("sesiones", distinct=True)
	).first()
	return render(
		request,
		"tracker/admin/entrenamiento_detalle.html",
		{
			"entrenamiento": entrenamiento,
			"form": form,
			"asignacion_form": asignacion_form,
			"ejercicio_form": ejercicio_form,
			"asignacion": asignacion,
			"ejercicios_rutina": EntrenamientoEjercicio.objects.filter(
				entrenamiento=entrenamiento
			)
			.select_related("ejercicio")
			.annotate(selecciones_activas=Count("elecciones", filter=Q(elecciones__activo=True)))
			.prefetch_related("elecciones__series"),
		},
	)


@staff_required
@require_http_methods(["POST"])
def entrenamiento_usuario_desasignar(request, entrenamiento_id, asignacion_id):
	asignacion = get_object_or_404(
		UsuarioEntrenamiento.objects.select_related("usuario", "entrenamiento"),
		entrenamiento_id=entrenamiento_id,
		pk=asignacion_id,
	)
	if asignacion.activa:
		asignacion.activa = False
		asignacion.save(update_fields=["activa"])
		messages.success(
			request,
			f"Rutina desasignada de {asignacion.usuario.username}. "
			"Las sesiones y el historial se han conservado.",
		)
	else:
		messages.info(request, "Esta rutina ya estaba desasignada de este usuario.")
	return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento_id)


@staff_required
@require_http_methods(["GET", "POST"])
def entrenamiento_ejercicio_editar(request, entrenamiento_id, entrada_id):
	entrenamiento = get_object_or_404(Entrenamiento, pk=entrenamiento_id)
	entrada = get_object_or_404(
		EntrenamientoEjercicio.objects.select_related("ejercicio"),
		pk=entrada_id,
		entrenamiento=entrenamiento,
	)
	form = AdminEntrenamientoEjercicioForm(
		request.POST or None, instance=entrada, entrenamiento=entrenamiento
	)
	if request.method == "POST" and form.is_valid():
		try:
			form.save()
		except IntegrityError:
			form.add_error(None, "El ejercicio o el orden ya están asignados a esta rutina.")
		else:
			messages.success(request, "El ejercicio de la rutina se actualizó.")
			return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)
	return render(
		request,
		"tracker/admin/entidad_form.html",
		{
			"form": form,
			"titulo": f"Editar ejercicio de {entrenamiento.nombre}",
			"volver": reverse("panel_admin:entrenamiento_detalle", args=[entrenamiento.pk]),
		},
	)


@staff_required
@require_http_methods(["POST"])
def entrenamiento_ejercicio_eliminar(request, entrenamiento_id, entrada_id):
	entrenamiento = get_object_or_404(Entrenamiento, pk=entrenamiento_id)
	entrada = get_object_or_404(
		EntrenamientoEjercicio, pk=entrada_id, entrenamiento=entrenamiento
	)
	selecciones = UsuarioEntrenamientoEjercicio.objects.filter(entrenamiento_ejercicio=entrada)
	with transaction.atomic():
		selecciones_con_historial = selecciones.filter(series__isnull=False).distinct()
		tiene_historial = selecciones_con_historial.exists()
		selecciones.filter(series__isnull=True).delete()
		selecciones_con_historial.update(activo=False)
		if not tiene_historial:
			entrada.delete()
	if tiene_historial:
		messages.success(
			request,
			"Ejercicio retirado de futuras sesiones; el historial se ha conservado.",
		)
	else:
		messages.success(request, "Ejercicio retirado de la rutina.")
	return redirect("panel_admin:entrenamiento_detalle", entrenamiento_id=entrenamiento.pk)


@staff_required
def sesiones(request):
	queryset = SesionEntrenamiento.objects.select_related(
		"usuario_entrenamiento__usuario", "usuario_entrenamiento__entrenamiento"
	).annotate(series_count=Count("series")).order_by("-fecha")
	usuario_id = request.GET.get("usuario", "")
	rutina_id = request.GET.get("rutina", "")
	if usuario_id.isdigit():
		queryset = queryset.filter(usuario_entrenamiento__usuario_id=int(usuario_id))
	if rutina_id.isdigit():
		entrenamiento = Entrenamiento.objects.filter(pk=int(rutina_id)).first()
		if entrenamiento is not None:
			queryset = queryset.filter(
				usuario_entrenamiento__entrenamiento_id=entrenamiento.pk
			)
	return render(
		request,
		"tracker/admin/sesiones.html",
		{
			"page_obj": Paginator(queryset, 30).get_page(request.GET.get("page")),
			"usuarios": get_user_model().objects.order_by("username"),
			"entrenamientos": Entrenamiento.objects.annotate(
				usuario_nombre=Min(
					"usuarios__usuario__username",
					filter=Q(usuarios__activa=True),
				)
			).order_by("nombre", "pk"),
			"usuario_id": usuario_id,
			"rutina_id": rutina_id,
		},
	)


@staff_required
@require_http_methods(["GET", "POST"])
def sesion_nueva(request):
	form = AdminSesionForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		sesion = form.save()
		messages.success(request, "La sesión se creó.")
		return redirect("panel_admin:sesion_detalle", sesion_id=sesion.pk)
	return render(
		request,
		"tracker/admin/entidad_form.html",
		{"form": form, "titulo": "Nueva sesión", "volver": reverse("panel_admin:sesiones")},
	)


@staff_required
@require_http_methods(["GET", "POST"])
def sesion_detalle(request, sesion_id):
	sesion = get_object_or_404(
		SesionEntrenamiento.objects.select_related(
			"usuario_entrenamiento__usuario", "usuario_entrenamiento__entrenamiento"
		),
		pk=sesion_id,
	)
	action = request.POST.get("action") if request.method == "POST" else None
	sesion_form = AdminSesionForm(
		request.POST if action == "guardar_sesion" else None,
		instance=sesion,
	)
	serie_form = AdminSerieForm(
		request.POST if action == "anadir_serie" else None,
		sesion=sesion,
	)
	if action == "guardar_sesion" and sesion_form.is_valid():
		sesion_form.save()
		messages.success(request, "La sesión se actualizó.")
		return redirect("panel_admin:sesion_detalle", sesion_id=sesion.pk)
	if action == "anadir_serie" and serie_form.is_valid():
		serie = serie_form.save(commit=False)
		serie.sesion_entrenamiento = sesion
		try:
			serie.save()
		except IntegrityError:
			serie_form.add_error(
				None, "Ya existe ese número de serie para este ejercicio en la sesión."
			)
		else:
			messages.success(request, "Serie añadida a la sesión.")
			return redirect("panel_admin:sesion_detalle", sesion_id=sesion.pk)
	return render(
		request,
		"tracker/admin/sesion_detalle.html",
		{
			"sesion": sesion,
			"sesion_form": sesion_form,
			"serie_form": serie_form,
			**_sesion_series_context(sesion),
		},
	)


def _sesion_series_context(sesion):
	series = list(
		sesion.series.select_related(
			"usuario_entrenamiento_ejercicio__entrenamiento_ejercicio__ejercicio"
		).order_by(
			"usuario_entrenamiento_ejercicio__entrenamiento_ejercicio__orden",
			"usuario_entrenamiento_ejercicio__entrenamiento_ejercicio__ejercicio__nombre",
			"numero_serie",
		)
	)
	series_por_ejercicio = []
	for serie in series:
		seleccion = serie.usuario_entrenamiento_ejercicio
		if (
			not series_por_ejercicio
			or series_por_ejercicio[-1]["seleccion_id"] != seleccion.pk
		):
			series_por_ejercicio.append(
				{
					"seleccion_id": seleccion.pk,
					"ejercicio": seleccion.entrenamiento_ejercicio.ejercicio,
					"series": [],
				}
			)
		series_por_ejercicio[-1]["series"].append(serie)
	return {
		"series": series,
		"series_por_ejercicio": series_por_ejercicio,
		"series_count": len(series),
	}


@staff_required
@require_http_methods(["GET", "POST"])
def serie_editar(request, serie_id):
	serie = get_object_or_404(
		Serie.objects.select_related("sesion_entrenamiento"), pk=serie_id
	)
	form = AdminSerieForm(request.POST or None, instance=serie, sesion=serie.sesion_entrenamiento)
	if request.method == "POST" and form.is_valid():
		try:
			form.save()
		except IntegrityError:
			form.add_error(
				None, "Ya existe ese número de serie para este ejercicio en la sesión."
			)
		else:
			messages.success(request, "La serie se actualizó.")
			return redirect("panel_admin:sesion_detalle", sesion_id=serie.sesion_entrenamiento_id)
	return render(
		request,
		"tracker/admin/entidad_form.html",
		{
			"form": form,
			"titulo": "Editar serie",
			"volver": reverse("panel_admin:sesion_detalle", args=[serie.sesion_entrenamiento_id]),
		},
	)


@staff_required
@require_http_methods(["POST"])
def serie_eliminar(request, sesion_id, serie_id):
	sesion = get_object_or_404(SesionEntrenamiento, pk=sesion_id)
	serie = get_object_or_404(Serie, pk=serie_id, sesion_entrenamiento=sesion)
	ejercicio = serie.usuario_entrenamiento_ejercicio.entrenamiento_ejercicio.ejercicio.nombre
	eliminar_serie_y_reenumerar(serie)
	messages.success(request, f"Serie eliminada de {ejercicio}.")
	return redirect("panel_admin:sesion_detalle", sesion_id=sesion.pk)