from django.utils.timezone import now

from chat.models import RequestRent
from influencer.models import PromoCode, UsedPromoCode


def check_promocode(user, promocode):
    """
    Проверка промокода при отправке заявки
    :param user:
    :param promocode:
    :return:
    """
    # Пользователь является арендатором
    if not hasattr(user, 'renter'):
        return "Промокод недействителен. Вы не являетесь арендатором."

    # Поиск промокода
    try:
        promo_code = PromoCode.objects.get(title=promocode)
    except PromoCode.DoesNotExist:
        return "Промокод не найден."

    # Проверка срока действия промокода
    if promo_code.expiration_date and promo_code.expiration_date < now():
        return "Срок действия промокода истек."

    # ИЗМЕНЕНИЕ: Строгая проверка использования промокода
    used_promo = UsedPromoCode.objects.filter(user=user, promo_code=promo_code).first()

    if used_promo:
        if used_promo.used:
            return "Промокод уже использован."
        # Если used_promo.used == False, значит промокод применен, но не использован - это OK
    else:
        # Если записи вообще нет, значит промокод не был применен
        return "Промокод не применен. Нажмите на кнопку применить."

    # Дополнительная проверка: нет ли активных заявок с этим промокодом у данного пользователя
    # active_request_with_promo = RequestRent.objects.filter(
    #     organizer=user,
    #     promocode=promo_code,
    #     status__in=['unknown', 'accept'],
    #     is_deleted=False
    # ).exists()
    #
    # if active_request_with_promo:
    #     return "У вас уже есть активная заявка с этим промокодом."

    return promo_code
