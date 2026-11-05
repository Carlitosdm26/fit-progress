from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import AdminUsuarioCreationForm, AdminUsuarioUpdateForm
from .models import Ejercicio, Entrenamiento, SesionEntrenamiento


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
	form = AdminUsuarioCreationForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		usuario = form.save()
		messages.success(request, f"La cuenta {usuario.username} se creó correctamente.")
		return redirect("panel_admin:usuario_editar", user_id=usuario.pk)
	return render(request, "tracker/admin/usuario_form.html", {"form": form, "nuevo": True})


@staff_required
@require_http_methods(["GET", "POST"])
def usuario_editar(request, user_id):
	User = get_user_model()
	usuario = get_object_or_404(User, pk=user_id)
	form = AdminUsuarioUpdateForm(request.POST or None, instance=usuario)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, f"La cuenta {usuario.username} se actualizó correctamente.")
		return redirect("panel_admin:usuario_editar", user_id=usuario.pk)
	return render(
		request,
		"tracker/admin/usuario_form.html",
		{"form": form, "nuevo": False, "usuario": usuario},
	)