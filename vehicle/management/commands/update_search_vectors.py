from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from django.db import models
from vehicle.models import VehicleModel, VehicleBrand
from transliterate import translit


class Command(BaseCommand):
    help = 'Updates search vectors for vehicle brands and models'

    def handle(self, *args, **kwargs):
        """ Обновление вектороов поиска """
        self.stdout.write('Updating search vectors...')

        for model in VehicleModel.objects.select_related('brand').iterator():
            combined_text = f"{model.name} {model.brand.name}"
            VehicleModel.objects.filter(pk=model.pk).update(search_vector=SearchVector(
                    models.Value(combined_text), config='russian'
                )
            )
        model_count = VehicleModel.objects.count()

        for brand in VehicleBrand.objects.all().iterator():
            text = brand.name
            VehicleBrand.objects.filter(pk=brand.pk).update(search_vector=SearchVector(
                    models.Value(text), config='russian'
                )
            )

        self.stdout.write(f'Updated {model_count} models')
        self.stdout.write(self.style.SUCCESS('Successfully updated all search vectors'))

    # def handle(self, *args, **kwargs):
    #     """ Обновление векторов поиска с поддержкой русского языка """
    #     self.stdout.write('Updating search vectors...')
    #
    #     for brand in VehicleBrand.objects.all().iterator():
    #         brand_en = f"{brand.name}"
    #         brand_ru = translit(brand_en, language_code='ru')
    #         VehicleBrand.objects.filter(pk=brand.pk).update(
    #             search_vector=(
    #                     SearchVector(models.Value(brand_en), config='english') +
    #                     SearchVector(models.Value(brand_ru), config='russian')
    #             )
    #         )
    #
    #     for model in VehicleModel.objects.select_related('brand').iterator():
    #         combined_text_en = f"{model.name} {model.brand.name}"
    #         combined_text_ru_translit = translit(combined_text_en, language_code='ru')
    #
    #         VehicleModel.objects.filter(pk=model.pk).update(
    #             search_vector=(
    #                     SearchVector(models.Value(combined_text_en), config='english') +
    #                     SearchVector(models.Value(combined_text_ru_translit), config='russian')
    #                 )
    #         )
    #     model_count = VehicleModel.objects.count()
    #     self.stdout.write(f'Updated {model_count} models')
    #     self.stdout.write(self.style.SUCCESS('Successfully updated all search vectors'))
