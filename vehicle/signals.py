from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector
from transliterate import translit

from vehicle.models import VehicleBrand, VehicleModel


# @receiver(post_save, sender=VehicleBrand)
# def update_brand_search_vector(sender, instance, **kwargs):
#     name_translit = translit(instance.name, language_code='ru')
#
#     instance.search_vector = (
#             SearchVector(models.Value(instance.name), config='english') +
#             SearchVector(models.Value(name_translit), config='russian')
#     )
#     instance.save(update_fields=['search_vector'])
#
#
# @receiver(post_save, sender=VehicleModel)
# def update_model_search_vector(sender, instance, **kwargs):
#     model_name_translit = translit(instance.name, language_code='ru')
#     brand_name_translit = translit(instance.brand.name, language_code='ru')
#
#     instance.search_vector = (
#             SearchVector(models.Value(instance.name), config='english') +
#             SearchVector(models.Value(instance.brand.name), config='english') +
#             SearchVector(models.Value(model_name_translit), config='russian') +
#             SearchVector(models.Value(brand_name_translit), config='russian')
#     )
#     instance.save(update_fields=['search_vector'])

_is_updating_search_vector = False


@receiver(post_save, sender=VehicleBrand)
def update_brand_search_vector(sender, instance, **kwargs):
    global _is_updating_search_vector
    if _is_updating_search_vector:
        return
    _is_updating_search_vector = True
    try:
        instance.search_vector = SearchVector('name', config='english')
        instance.save()
    finally:
        _is_updating_search_vector = False


processed_objects = set()


@receiver(post_save, sender=VehicleModel)
def update_model_search_vector(sender, instance, **kwargs):
    if instance.pk in processed_objects:
        return
    processed_objects.add(instance.pk)
    model_instance = VehicleModel.objects.annotate(
        combined_search=SearchVector('name', config='english') +
                        SearchVector('brand__name', config='english')
    ).get(pk=instance.pk)

    model_instance.search_vector = model_instance.combined_search
    model_instance.save()

    transaction.on_commit(lambda: processed_objects.discard(instance.pk))