import math

from django.db.models import Q
from django_filters import rest_framework as filters
from haversine import haversine, Unit

from vehicle.models import AutoFeaturesAdditionally, Auto, Bike, Ship, Helicopter, SpecialTechnic, VehicleModel, \
    BikeFeaturesAdditionally, ShipFeaturesAdditionally, FeaturesForChildren, \
    FeaturesEquipment, VehicleBrand, AutoFeaturesFunctions, BikeFeaturesFunctions, ShipFeaturesFunctions


class BaseFilter(filters.FilterSet):
    super_host = filters.BooleanFilter(field_name='owner__lessor__super_host', label='Суперхост')
    day_price = filters.RangeFilter(field_name='rent_prices__total', label='Дневная цена')
    verified_only = filters.BooleanFilter(field_name='drivers_only_verified',
                                          label='Сдается только верифицированным пользователям')
    brand = filters.CharFilter(method='filter_by_brand', label='Марка')
    year = filters.RangeFilter(field_name='year', label='Год выпуска')
    rental_date = filters.DateFromToRangeFilter(method='filter_by_rental_date', label='Выбор даты аренды')
    city = filters.NumberFilter(field_name='city__id', label='Город')

    lat = filters.NumberFilter(method='filter_by_lat_lon', label='Широта')
    lon = filters.NumberFilter(method='filter_by_lat_lon', label='Долгота')
    radius = filters.NumberFilter(method='filter_by_lat_lon', label='Радиус в км', required=False)

    delivery = filters.BooleanFilter(field_name='delivery')
    ensurance = filters.CharFilter(field_name='ensurance')
    long_distance = filters.BooleanFilter(field_name='long_distance')
    average_rating = filters.RangeFilter(field_name='average_rating', label='Средняя оценка')
    verified = filters.BooleanFilter(field_name='verified', label='Верифицированный транспорт')

    class Meta:
        abstract = True

    def filter_by_rental_date(self, queryset, name, value):
        """
        Фильтрация по диапазону дат аренды, с добавлением объектов, у которых on_request=True.
        """
        if value.start and value.stop:
            queryset = queryset.filter(
                Q(availabilities__start_date__lte=value.start, availabilities__end_date__gte=value.stop) |
                Q(availabilities__on_request=True)
            )
        elif value.start:
            queryset = queryset.filter(
                Q(availabilities__start_date__lte=value.start) | Q(availabilities__on_request=True)
            )
        elif value.stop:
            queryset = queryset.filter(
                Q(availabilities__end_date__gte=value.stop) | Q(availabilities__on_request=True)
            )
        return queryset.distinct()

    def filter_by_brand(self, queryset, name, value):
        brand_names = value.split(",")
        return queryset.filter(brand__name__in=brand_names)

    def filter_by_lat_lon(self, queryset, name, value):
        """ Фильтрация транспортных средств в заданном радиусе от указанной точки. """
        lat = self.data.get('lat')
        lon = self.data.get('lon')
        radius = self.data.get('radius', 5)  # Радиус по умолчанию 5 км

        if lat and lon:
            try:
                lat = float(lat)
                lon = float(lon)
                radius = float(radius)

                km_per_degree_lat = 111.0
                # Один градус долготы зависит от широты (сужается к полюсам)
                km_per_degree_lon = 111.0 * math.cos(math.radians(lat))

                # Вычисляем границы координат для предварительной фильтрации
                lat_delta = radius / km_per_degree_lat
                lon_delta = radius / km_per_degree_lon

                lat_min = lat - lat_delta
                lat_max = lat + lat_delta
                lon_min = lon - lon_delta
                lon_max = lon + lon_delta

                # Предварительная фильтрация по ограничивающему прямоугольнику
                filtered_qs = queryset.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                    latitude__gte=lat_min,
                    latitude__lte=lat_max,
                    longitude__gte=lon_min,
                    longitude__lte=lon_max
                )

                # Точная фильтрация по формуле гаверсинуса с использованием базы данных
                earth_radius = 6371

                from django.db.models.expressions import RawSQL
                distance_sql = f"""
                {earth_radius} * 2 * ASIN(
                    SQRT(
                        POWER(SIN(RADIANS(%s - latitude) / 2), 2) +
                        COS(RADIANS(%s)) * COS(RADIANS(latitude)) *
                        POWER(SIN(RADIANS(%s - longitude) / 2), 2)
                    )
                )
                """

                filtered_qs = filtered_qs.annotate(
                    distance=RawSQL(distance_sql, [lat, lat, lon])
                ).filter(distance__lte=radius)

                return filtered_qs

            except (ValueError, TypeError):
                return queryset

        return queryset


class AutoFilter(BaseFilter):

    mileage_per_day = filters.RangeFilter(field_name='acceptable_mileage', label='Допустимый пробег/день')
    vehicle_class = filters.CharFilter(field_name='vehicle_class__slug', label='Класс транспорта')
    fuel_type = filters.CharFilter(field_name='fuel_type__slug', label='Тип топлива')
    seat_count = filters.RangeFilter(field_name='seats', label='Количество мест')
    transmission = filters.CharFilter(field_name='transmission__slug', label='Трансмиссия')
    body_type = filters.CharFilter(field_name='body_type__slug', label='Тип кузова')
    features_additionally = filters.ModelMultipleChoiceFilter(
        field_name='features_additionally__id',
        queryset=AutoFeaturesAdditionally.objects.all(),
        to_field_name='id',
        label='Выбор особенностей'
    )
    features_for_children = filters.ModelMultipleChoiceFilter(
        field_name='features_for_children__id',
        queryset=FeaturesForChildren.objects.all(),
        to_field_name='id',
        label='Для детей'
    )
    features_functions = filters.ModelMultipleChoiceFilter(
        field_name='features_functions__id',
        queryset=AutoFeaturesFunctions.objects.all(),
        to_field_name='id',
        label='Функции'
    )

    class Meta:
        model = Auto
        fields = [
            'day_price', 'verified_only', 'mileage_per_day', 'rental_date', 'features_for_children',
            'features_functions', 'vehicle_class', 'features_additionally', 'fuel_type', 'brand', 'seat_count',
            'transmission', 'year', 'super_host', 'average_rating'
        ]


class BikeFilter(BaseFilter):
    mileage_per_day = filters.RangeFilter(field_name='acceptable_mileage', label='Допустимый пробег/день')
    vehicle_class = filters.CharFilter(field_name='vehicle_class__slug', label='Класс транспорта')
    engine_capacity = filters.RangeFilter(field_name='engine_capacity', label='Объем двигателя')
    seat_count = filters.RangeFilter(field_name='seat_count', label='Количество мест')
    transmission = filters.CharFilter(field_name='transmission__slug', label='Трансмиссия')
    body_type = filters.NumberFilter(field_name='body_type__id', label='Тип мотоцикла')
    features_additionally = filters.ModelMultipleChoiceFilter(
        field_name='features_additionally__id',
        queryset=BikeFeaturesAdditionally.objects.all(),
        to_field_name='id',
        label='Выбор особенностей'
    )
    features_functions = filters.ModelMultipleChoiceFilter(
        field_name='features_functions__id',
        queryset=BikeFeaturesFunctions.objects.all(),
        to_field_name='id',
        label='Функции'
    )

    class Meta:
        model = Bike
        fields = [
            'day_price', 'super_host', 'mileage_per_day', 'rental_date', 'features_functions',
            'vehicle_class', 'features_additionally', 'engine_capacity', 'brand',
            'year', 'seat_count', 'transmission'
        ]

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return queryset.distinct()


class ShipFilter(BaseFilter):
    mileage_per_day = filters.RangeFilter(field_name='acceptable_mileage', label='Допустимый пробег/день')
    vehicle_class = filters.CharFilter(field_name='vehicle_class__slug', label='Класс транспорта')
    engine_capacity = filters.RangeFilter(field_name='engine_capacity', label='Объем двигателя')
    grot = filters.CharFilter(field_name='grot', label='Грот')
    type_ship = filters.NumberFilter(field_name='type_ship__id', label='Тип судна')
    features_additionally = filters.ModelMultipleChoiceFilter(
        field_name='features_additionally__id',
        queryset=ShipFeaturesAdditionally.objects.all(),
        to_field_name='id',
        label='Выбор особенностей'
    )
    features_functions = filters.ModelMultipleChoiceFilter(
        field_name='features_functions__id',
        queryset=ShipFeaturesFunctions.objects.all(),
        to_field_name='id',
        label='Функции'
    )
    features_equipment = filters.ModelMultipleChoiceFilter(
        field_name='features_equipment__id',
        queryset=FeaturesEquipment.objects.all(),
        to_field_name='id',
        label='Оборудование'
    )

    class Meta:
        model = Ship
        fields = [
            'day_price', 'super_host', 'mileage_per_day', 'rental_date', 'features_functions', 'features_equipment',
            'vehicle_class', 'features_additionally', 'engine_capacity', 'brand', 'year', 'type_ship', 'grot']


class HelicopterFilter(BaseFilter):
    mileage_per_day = filters.RangeFilter(field_name='acceptable_mileage', label='Допустимый пробег/день')
    vehicle_class = filters.CharFilter(field_name='vehicle_class__slug', label='Класс транспорта')
    engine_capacity = filters.RangeFilter(field_name='engine_capacity', label='Объем двигателя')
    max_speed = filters.RangeFilter(field_name='max_speed', label='Максимальная скорость, км/ч')
    full_take_weight = filters.RangeFilter(field_name='full_take_weight', label='Полный взлетный вес, кг')

    class Meta:
        model = Helicopter
        fields = [
            'day_price', 'super_host', 'mileage_per_day', 'rental_date', 'vehicle_class', 'engine_capacity', 'brand',
            'year', 'max_speed', 'full_take_weight']


class SpecialTechnicFilter(BaseFilter):
    engine_power = filters.RangeFilter(field_name='engine_power', label='Мощность двигателя, л.с.')
    operating_weight = filters.RangeFilter(field_name='operating_weight', label='Эксплутационная масса, кг')
    type_technic = filters.NumberFilter(field_name='type_technic__id', label='Тип судна')

    class Meta:
        model = SpecialTechnic
        fields = [
            'day_price', 'super_host', 'rental_date', 'brand',
            'year', 'type_technic', 'engine_power', 'operating_weight']


class VehicleModelFilter(filters.FilterSet):
    vehicle_type = filters.ChoiceFilter(choices=VehicleModel.VEHICLE_TYPES, label="Тип транспорта")

    class Meta:
        model = VehicleModel
        fields = ['vehicle_type']


class VehicleBrandFilter(filters.FilterSet):
    category = filters.ChoiceFilter(choices=VehicleModel.VEHICLE_TYPES, label="Тип транспорта", method='filter_by_category')

    def filter_by_category(self, queryset, name, value):
        return queryset.filter(transport_categories__name=value)

    class Meta:
        model = VehicleBrand
        fields = ['category']
