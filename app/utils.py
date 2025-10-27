from typing import Union, Dict, Any
from django.db.models import Model

from app.models import User
from influencer.models import ReferralLink, QRCode, PromoCode, UsedPromoCode


def increment_count(obj: Model) -> None:
    """Увеличивает счётчик и сохраняет объект."""
    obj.count += 1
    obj.save()


def referal_check(user: User, ref: str = None, referral_code: str = None, promocode: str = None):
    try:
        renter = user.renter
        print(f"Заходим в функцию {ref}, {referral_code}, {promocode}")
        if ref and referral_code:
            print("Проверяем ссылки")
            # Проверяем реферальную ссылку
            referral_link = ReferralLink.objects.filter(influencer__referral_code=ref, link__icontains=referral_code).first()
            if referral_link:
                increment_count(referral_link)
                renter.influencer = referral_link.influencer
                renter.save()
            else:
                qr_code = QRCode.objects.filter(influencer__referral_code=ref, referral_link__icontains=referral_code).first()
                if qr_code:
                    increment_count(qr_code)
                    renter.influencer = qr_code.influencer
                    renter.save()
                else:
                    pass
        elif promocode:
            print(f"Проверяем промокод {promocode}")
            promo = PromoCode.objects.filter(title=promocode).first()
            if not promo:
                print(f"Promo code not found: {promocode}")
                return
            print(f"Promo code found: {promo.title}")

            increment_count(promo)

            if promo.type == 'cash' and hasattr(user, 'renter'):
                # Добавляем бонусы пользователю
                renter = user.renter
                renter.bonus_account = promo.total
                renter.save()
                # Отмечаем использование промокода
                UsedPromoCode.objects.create(user=user, promo_code=promo, used=True)
            else:
                UsedPromoCode.objects.create(user=user, promo_code=promo)
            # Привязываем инфлюенсера, если есть
            if promo.influencer:
                renter.influencer = promo.influencer
                renter.save()
    except Exception:
        pass