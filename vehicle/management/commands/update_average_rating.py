from django.core.management.base import BaseCommand
from vehicle.models import Vehicle


class Command(BaseCommand):
    help = 'Пересчитывает поле average_rating на основе JSON-поля ratings'

    def handle(self, *args, **kwargs):
        updated = 0
        skipped = 0

        vehicles = Vehicle.objects.all()
        total = vehicles.count()

        self.stdout.write(f"Обновление рейтингов для {total} транспортных средств...")

        for vehicle in vehicles:
            try:
                avg = vehicle.get_average_rating().get('rating', 0) or 0
                vehicle.average_rating = avg
                vehicle.save(update_fields=['average_rating'])
                updated += 1
            except Exception as e:
                self.stderr.write(f"Ошибка при обработке ID={vehicle.id}: {e}")
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Готово! Обновлено: {updated}, Пропущено из-за ошибок: {skipped}"
        ))
