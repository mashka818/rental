from django.contrib import admin
from django.db.models import Q

from vehicle.models import Vehicle
from .models import Franchise, VehiclePark, RequestFranchise, Category, City


class CityAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)
    ordering = ('title',)


# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ('name',)
#     search_fields = ('name',)
#     ordering = ('name',)


# class VehicleAdmin(admin.ModelAdmin):
#     list_display = (
#         'brand', 'model', 'year', 'owner'
#     )
#     search_fields = ('brand', 'model', 'owner__email')
#     list_filter = ('owner',)


# Inline class for VehiclePark
# class VehicleParkInline(admin.TabularInline):
#     model = VehiclePark
#     extra = 1
#     readonly_fields = ('name',)


class FranchiseAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'inn', 'date_register', 'telephone_1', 'email_1', 'country', 'city',
        'director', 'commission', 'total_vehicles', 'get_vehicles'
    )
    list_filter = ('country', 'city', 'director')
    search_fields = ('name', 'inn', 'email_1', 'telephone_1', 'country', 'city', 'director__email')
    readonly_fields = ('total_vehicles', 'date_register')

    #inlines = [VehicleParkInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            obj.save_total_vehicles()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('vehicle_parks', 'lessors')

    def get_vehicles(self, obj):
        vehicles = Vehicle.objects.filter(
            Q(owner__lessor__franchise=obj) | Q(owner=obj.director)
        )
        return ", ".join([f'{v.brand} {v.model} ({v.year})' for v in vehicles])
    get_vehicles.short_description = 'Транспортные средства'

    def get_fieldsets(self, request, obj=None):
        return [
            ('Основная информация', {
                'fields': (
                    'name', 'inn', 'date_register', 'country', 'city', 'address',
                    'director', 'commission', 'total_vehicles'
                )
            }),
            ('Контактная информация', {
                'fields': (
                    'telephone_1', 'telephone_2', 'email_1', 'email_2'
                )
            }),
            ('Банковские реквизиты', {
                'fields': (
                    'ogrn', 'account_number', 'account_owner'
                )
            }),
            ('Категории', {
                'fields': ('categories',)
            }),
        ]


# class VehicleParkAdmin(admin.ModelAdmin):
#     list_display = ('name', 'owner', 'franchise')
#     list_filter = ('owner', 'franchise')
#     search_fields = ('name', 'owner__email', 'franchise__name')


class RequestFranchiseAdmin(admin.ModelAdmin):
    list_display = ('name', 'telephone', 'email', 'city')
    search_fields = ('name', 'telephone', 'email', 'city')


# admin.site.register(Category, CategoryAdmin)
admin.site.register(Franchise, FranchiseAdmin)
# admin.site.register(VehiclePark, VehicleParkAdmin)
admin.site.register(RequestFranchise, RequestFranchiseAdmin)
admin.site.register(City, CityAdmin)
