from abc import ABC, abstractmethod
from datetime import datetime, timedelta, date

from chat.models import RequestRent
from influencer.models import PromoCode


def subtract_periods(periods, sub_period):
    """ Проверка вхождения периода в массив. Если период выходит в массив, то даный период вычитается из массива"""
    result = []
    complete_containment = False

    sub_start = datetime.strptime(sub_period['start_date'], '%Y-%m-%d')
    sub_end = datetime.strptime(sub_period['end_date'], '%Y-%m-%d')

    for period in periods:
        start = datetime.strptime(period['start_date'], '%Y-%m-%d')
        end = datetime.strptime(period['end_date'], '%Y-%m-%d')

        # Проверяем, содержится ли субпериод полностью внутри текущего периода
        if start <= sub_start and end >= sub_end:
            complete_containment = True

        # Если субпериод полностью вне текущего периода, просто добавляем текущий период
        if sub_end < start or sub_start > end:
            result.append(period)
        else:
            # Если субпериод перекрывает начало текущего периода
            if sub_start > start and sub_start <= end:
                result.append(
                    {'start_date': period['start_date'], 'end_date': (sub_start - timedelta(days=1)).strftime('%Y-%m-%d')})
            # Если субпериод перекрывает конец текущего периода
            if sub_end >= start and sub_end < end:
                result.append({'start_date': (sub_end + timedelta(days=1)).strftime('%Y-%m-%d'), 'end_date': period['end_date']})
            # Если субпериод находится внутри текущего периода, создаем два новых периода
            if sub_start > start and sub_end < end:
                result.append(
                    {'start_date': period['start_date'], 'end_date': (sub_start - timedelta(days=1)).strftime('%Y-%m-%d')})
                result.append({'start_date': (sub_end + timedelta(days=1)).strftime('%Y-%m-%d'), 'end_date': period['end_date']})

    if not complete_containment:
        return "требуемый период времени недоступен"

    # Удаляем дублирующиеся периоды (если они возникли)
    unique_result = []
    seen = set()
    for r in result:
        r_tuple = (r['start_date'], r['end_date'])
        if r_tuple not in seen:
            seen.add(r_tuple)
            unique_result.append(r)

    return unique_result


def is_period_contained(periods, sub_period):
    sub_start = datetime.strptime(sub_period['start_date'], '%Y-%m-%d')
    sub_end = datetime.strptime(sub_period['end_date'], '%Y-%m-%d')

    for period in periods:
        start = datetime.strptime(period['start_date'], '%Y-%m-%d')
        end = datetime.strptime(period['end_date'], '%Y-%m-%d')

        # Проверяем, входит ли субпериод в текущий период
        if start <= sub_start and end >= sub_end:
            return True

    return False


def calculate_age(birth_date):
    if birth_date is None:
        return 0
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age


class PromoCodeStrategy(ABC):
    @abstractmethod
    def apply(self, amount: float, promo_code: PromoCode, bonus_account) -> float:
        """Применяет промокод и возвращает обновленную сумму"""
        pass


class PercentDiscountStrategy(PromoCodeStrategy):
    def apply(self, amount: float, promo_code: PromoCode, bonus_account) -> float:
        discount = amount * (promo_code.total / 100)
        return max(amount - discount, 0)
