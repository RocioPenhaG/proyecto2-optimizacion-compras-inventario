from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Django 5.x: el alta en admin usa campos como usable_password del AdminUserCreationForm.
    add_form = AdminUserCreationForm

    list_display = ["username", "email", "first_name", "last_name", "role", "is_staff"]
    list_filter = ["role", "is_staff"]
    fieldsets = BaseUserAdmin.fieldsets + (("Rol", {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Rol", {"fields": ("role",)}),)
