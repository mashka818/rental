from django.contrib import admin
from .models import Manager, ManagerDocuments, AccessType


# class AccessTypeInline(admin.TabularInline):
#     model = Manager.access_types.through
#     extra = 1
#
#
# class CityInline(admin.TabularInline):
#     model = Manager.cities.through
#     extra = 1


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_cities', 'get_access_types_count')
    #inlines = [CityInline, AccessTypeInline]
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    list_filter = ('cities', 'access_types')
    filter_horizontal = ('cities', 'access_types')

    def get_cities(self, obj):
        """Отображение списка городов менеджера"""
        cities = obj.cities.all()
        if cities:
            return ', '.join([city.title for city in cities])
        return 'Не назначен'

    get_cities.short_description = 'Города'

    def get_access_types_count(self, obj):
        """Количество типов доступа"""
        return obj.access_types.count()

    get_access_types_count.short_description = 'Кол-во доступов'


@admin.register(ManagerDocuments)
class ManagerDocumentsAdmin(admin.ModelAdmin):
    list_display = ['manager', 'number']
    search_fields = ('manager__user__first_name', 'manager__user__last_name', 'number')


@admin.register(AccessType)
class AccessTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'permission', 'get_managers_count')
    list_filter = ('name', 'permission')
    search_fields = ('name',)
    ordering = ('name', 'permission')

    def get_managers_count(self, obj):
        """Количество менеджеров с данным типом доступа"""
        return obj.managers.count()

    get_managers_count.short_description = 'Кол-во менеджеров'
