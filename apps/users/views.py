from django.views.generic import CreateView, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import redirect
from django.contrib import messages
from .models import UserProfile, PropertyFavorite, PropertyInquiry


class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = 'users/register.html'

    def form_valid(self, form):
        user = form.save()
        # Создаем профиль пользователя
        UserProfile.objects.create(user=user)
        login(self.request, user)
        messages.success(self.request, 'Добро пожаловать! Ваш аккаунт создан.')
        return redirect('home')


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'users/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Статистика пользователя
        context['favorites_count'] = self.request.user.favorites.count()
        context['inquiries_count'] = PropertyInquiry.objects.filter(
            email=self.request.user.email
        ).count()

        return context


class FavoritesView(LoginRequiredMixin, ListView):
    template_name = 'users/favorites.html'
    context_object_name = 'favorites'
    paginate_by = 12

    def get_queryset(self):
        return PropertyFavorite.objects.filter(
            user=self.request.user
        ).select_related('property__district', 'property__property_type').prefetch_related('property__images').order_by(
            '-created_at')