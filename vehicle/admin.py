from django.contrib import admin
from django.contrib.contenttypes.admin import GenericStackedInline

from feedback.models import Feedback
from .models import *


class BaseFeatures(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)


class BaseType(admin.ModelAdmin):
    list_display = ('id', 'title', 'slug')
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ('title',)
    ordering = ('title',)

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = slugify(obj.title)
        super().save_model(request, obj, form, change)


@admin.register(VehicleCategory)
class VehicleCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(AutoFeaturesFunctions)
class AutoFeaturesFunctionsAdmin(BaseFeatures):
    pass


@admin.register(BikeFeaturesFunctions)
class BikeFeaturesFunctionsAdmin(BaseFeatures):
    pass


@admin.register(ShipFeaturesFunctions)
class ShipFeaturesFunctionsAdmin(BaseFeatures):
    pass


@admin.register(AutoFeaturesAdditionally)
class AutoFeaturesAdditionallyAdmin(BaseFeatures):
    pass


@admin.register(BikeFeaturesAdditionally)
class BikeFeaturesAdditionallyAdmin(BaseFeatures):
    pass


@admin.register(ShipFeaturesAdditionally)
class ShipFeaturesAdditionallyAdmin(BaseFeatures):
    pass


@admin.register(FeaturesForChildren)
class FeaturesForChildrenAdmin(BaseFeatures):
    pass


@admin.register(FeaturesEquipment)
class FeaturesEquipmentAdmin(BaseFeatures):
    pass


@admin.register(PaymentMethod)
class PaymentMethodAdmin(BaseFeatures):
    admin_order = 1
    pass


@admin.register(VehicleBrand)
class VehicleBrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'display_categories')
    search_fields = ('name',)
    ordering = ('name',)
    filter_horizontal = ('transport_categories',)
    list_filter = ('transport_categories',)
    admin_order = 3

    def display_categories(self, obj):
        """Выводим категории транспорта в списке"""
        return ", ".join([category.get_name_display() for category in obj.transport_categories.all()])

    display_categories.short_description = "Категории транспорта"


@admin.register(VehicleModel)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'vehicle_type', 'brand')
    search_fields = ('name',)
    list_filter = ('vehicle_type', 'brand')
    ordering = ('name',)
    admin_order = 4


@admin.register(VehicleClass)
class VehicleClassAdmin(BaseType):
    admin_order = 2
    pass


@admin.register(AutoFuelType)
class AutoFuelTypeAdmin(BaseType):
    pass


@admin.register(AutoTransmission)
class AutoTransmissionAdmin(BaseType):
    pass


@admin.register(AutoBodyType)
class AutoBodyTypeAdmin(BaseType):
    pass


@admin.register(BikeTransmission)
class BikeTransmissionAdmin(BaseType):
    pass


@admin.register(BikeBodyType)
class BikeBodyTypeAdmin(BaseType):
    pass


@admin.register(ShipType)
class ShipTypeAdmin(BaseType):
    pass


@admin.register(TechnicType)
class TechnicTypeAdmin(BaseType):
    pass


class FeedbackInline(GenericStackedInline):
    model = Feedback
    extra = 1


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 1


# class VehicleDocumentInline(admin.TabularInline):
#     model = VehicleDocument
#     extra = 1


class VehiclePhotoInline(admin.TabularInline):
    model = VehiclePhoto
    extra = 1


class RentPriceInline(admin.TabularInline):
    model = RentPrice
    extra = 1
    readonly_fields = ('total',)


class BaseVehicleAdmin(admin.ModelAdmin):
    list_display = ('brand', 'model', 'year', 'owner', 'city', 'id', 'get_average_rating', 'verified_text',)
    list_display_links = ('brand', 'model', 'owner', 'city',)
    search_fields = ('brand__name', 'model__name', 'year', 'owner__email', 'city__title', )
    list_filter = ('brand', 'model', 'year', 'owner', 'city__title', 'verified')
    ordering = ('-year',)
    list_per_page = 20
    readonly_fields = ('get_average_rating',)

    inlines = [AvailabilityInline, RentPriceInline, VehiclePhotoInline, FeedbackInline]  # VehicleDocumentInline

    def verified_text(self, obj):
        return "Да" if obj.verified else "Нет"

    verified_text.short_description = 'Верифицирован'

    def get_vehicle_type(self, obj):
        return obj.__class__.__name__

    get_vehicle_type.short_description = 'Тип транспорта'

    def get_average_rating(self, obj):
        average_ratings = obj.get_average_rating()
        return ', '.join(f"{category}: {rating:.1f}" for category, rating in average_ratings.items())

    get_average_rating.short_description = 'Рейтинг'

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj:
            fieldsets = list(fieldsets)
            fieldsets.append(('Рейтинг', {'fields': ('get_average_rating',)}))
        return fieldsets

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        availabilities = list(form.instance.availabilities.values('start_date', 'end_date', 'on_request'))

        if any(avail['on_request'] for avail in availabilities):
            form.instance.availabilities.exclude(on_request=True).delete()
        else:
            if availabilities:
                merged_availabilities = merge_periods(availabilities)
                form.instance.availabilities.all().delete()

                for availability in merged_availabilities:
                    Availability.objects.create(vehicle=form.instance, **availability)

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if not obj:
            inline_instances = [inline for inline in inline_instances if not isinstance(inline, FeedbackInline)]
        return inline_instances


class AutoAdmin(BaseVehicleAdmin):
    fieldsets = (
        (None, {
            'fields': ('owner', 'verified')
        }),
        ('Характеристики', {
            'fields': ('brand', 'model', 'body_type', 'seats', 'transmission', 'fuel_type',
                       'year', 'description', 'long_distance', 'delivery', 'ensurance', 'vehicle_class',
                       'acceptable_mileage')
        }),
        ('Особенности', {
            'fields': ('features_for_children', 'features_functions', 'features_additionally')
        }),
        ('Условия аренды', {
            'fields': ('drivers_age', 'drivers_experience', 'drivers_rating', 'drivers_only_verified')
        }),
        ('Цены и скидки', {
            'fields': ('price_delivery', 'price_deposit', 'min_rent_day', 'max_rent_day',)
        }),
        ('Способ оплаты', {
            'fields': ('payment_method',)
        }),
        ('Местоположение', {
            'fields': ('city', 'location', 'latitude', 'longitude')
        })
    )


class BikeAdmin(BaseVehicleAdmin):
    fieldsets = (
        (None, {
            'fields': ('owner', 'verified')
        }),
        ('Характеристики', {
            'fields': ('brand', 'model', 'body_type', 'seats', 'engine_capacity', 'transmission', 'year', 'description',
                       'long_distance', 'delivery', 'ensurance', 'vehicle_class', 'acceptable_mileage')
        }),
        ('Особенности', {
            'fields': ('features_functions', 'features_additionally')
        }),
        ('Условия аренды', {
            'fields': ('drivers_age', 'drivers_experience', 'drivers_rating', 'drivers_only_verified')
        }),
        ('Цены и скидки', {
            'fields': ('price_delivery', 'price_deposit', 'min_rent_day', 'max_rent_day',)
        }),
        ('Способ оплаты', {
            'fields': ('payment_method',)
        }),
        ('Местоположение', {
            'fields': ('city', 'location', 'latitude', 'longitude')
        })
    )


class ShipAdmin(BaseVehicleAdmin):
    fieldsets = (
        (None, {
            'fields': ('owner', 'verified')
        }),
        ('Характеристики', {
            'fields': ('brand', 'model', 'type_ship',  'year', 'grot', 'length', 'width', 'precipitation', 'seats',
                       'sleeping_place', 'one_sleeping_place', 'two_sleeping_place', 'toilet', 'engine_capacity',
                       'water_tank', 'fuel_tank', 'description', 'long_distance', 'delivery', 'ensurance',
                       'vehicle_class', 'acceptable_mileage')
        }),
        ('Особенности', {
            'fields': ('features_functions', 'features_additionally', 'features_equipment')
        }),
        ('Условия аренды', {
            'fields': ('drivers_rating', 'drivers_only_verified')
        }),
        ('Цены и скидки', {
            'fields': ('price_delivery', 'price_deposit', 'min_rent_day', 'max_rent_day',)
        }),
        ('Способ оплаты', {
            'fields': ('payment_method',)
        }),
        ('Местоположение', {
            'fields': ('city', 'location', 'latitude', 'longitude')
        })
    )


class HelicopterAdmin(BaseVehicleAdmin):
    fieldsets = (
        (None, {
            'fields': ('owner', 'verified')
        }),
        ('Характеристики', {
            'fields': ('brand', 'model', 'year', 'max_speed', 'cruising_speed', 'flight_range',
                       'flight_duration', 'power_cruising', 'take_off_power', 'full_take_weight', 'payload',
                       'engine_capacity', 'fuel_tank', 'description', 'long_distance', 'delivery', 'ensurance',
                       'vehicle_class', 'acceptable_mileage')
        }),
        ('Условия аренды', {
            'fields': ('drivers_rating', 'drivers_only_verified')
        }),
        ('Цены и скидки', {
            'fields': ('price_delivery', 'price_deposit', 'min_rent_day', 'max_rent_day',)
        }),
        ('Способ оплаты', {
            'fields': ('payment_method',)
        }),
        ('Местоположение', {
            'fields': ('city', 'location', 'latitude', 'longitude')
        })
    )


class SpecialTechnicAdmin(BaseVehicleAdmin):
    fieldsets = (
        (None, {
            'fields': ('owner', 'verified')
        }),
        ('Характеристики', {
            'fields': ('brand', 'model', 'type_technic', 'year', 'engine_power', 'length', 'width', 'high',
                       'operating_weight', 'description', 'long_distance', 'delivery', 'ensurance')
        }),
        ('Условия аренды', {
            'fields': ('drivers_rating', 'drivers_only_verified')
        }),
        ('Цены и скидки', {
            'fields': ('price_delivery', 'price_deposit', 'min_rent_day', 'max_rent_day',)
        }),
        ('Способ оплаты', {
            'fields': ('payment_method',)
        }),
        ('Местоположение', {
            'fields': ('city', 'location', 'latitude', 'longitude')
        })
    )


admin.site.register(Auto, AutoAdmin)
admin.site.register(Bike, BikeAdmin)
admin.site.register(Ship, ShipAdmin)
admin.site.register(Helicopter, HelicopterAdmin)
admin.site.register(SpecialTechnic, SpecialTechnicAdmin)
