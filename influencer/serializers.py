import random

from django.db.models import Sum
from django.utils.timezone import now
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from chat.models import Trip, RequestRent
from influencer.models import Influencer, ReferralLink, InfluencerRequest, QRCode, BankDetails, Organization, \
    InfluencerDocuments, PromoCode, RegistrationSource, RequestWithdraw
from manager.utils import generate_secure_password
from notification.models import Notification
from payment.models import Payment
from vehicle.models import Vehicle


class InfluencerListSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    date_of_birth = serializers.DateField(source='user.date_of_birth', read_only=True)
    avatar = serializers.ImageField(source='user.avatar', required=False, read_only=True)
    telephone = serializers.CharField(source='user.telephone', read_only=True)

    turnover = serializers.SerializerMethodField()
    income = serializers.SerializerMethodField()
    total_clicks = serializers.SerializerMethodField()

    class Meta:
        model = Influencer
        fields = [
            'id', 'user_id', 'email', 'first_name', 'last_name', 'turnover', 'income', 'total_clicks',
            'date_of_birth', 'avatar', 'telephone', 'referral_code', 'commission'
        ]

    def get_turnover(self, obj):
        """
        Возвращает оборот (turnover) для инфлюенсера.
        """
        from payment.models import Payment

        turnover = Payment.objects.filter(influencer=obj, status='success').aggregate(total=Sum('amount'))['total']
        return turnover or 0

    def get_income(self, obj):
        """
        Возвращает доход (income) для инфлюенсера.
        """
        turnover = self.get_turnover(obj)
        return round((float(turnover) / 100 * float(obj.commission)), 2) if turnover else 0

    def get_total_clicks(self, obj):
        """
        Возвращает общее количество кликов (total_clicks) для инфлюенсера.
        """
        from app.models import Renter, Lessor

        renter_clicks = Renter.objects.filter(influencer=obj).count()
        lessor_clicks = Lessor.objects.filter(influencer=obj).count()
        return renter_clicks + lessor_clicks


class InfluencerSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    telephone = serializers.CharField(source='user.telephone')

    class Meta:
        model = Influencer
        fields = ['id', 'email', 'first_name', 'last_name', 'referral_code', 'user_id', 'telephone']
        read_only_fields = ['id', 'referral_code']

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_data = validated_data.pop('user')
        email = user_data.get('email')
        first_name = user_data.get('first_name')
        last_name = user_data.get('last_name')
        telephone = user_data.get('telephone')

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "Пользователь с таким email уже зарегистрирован."})

        password = generate_secure_password()

        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            telephone=telephone,
            role='member',
        )

        influencer = Influencer.objects.create(user=user, **validated_data)

        Notification.objects.create(
            user=user,
            content=f"Добро пожаловать, {first_name}! Вы успешно зарегистрированы как партнер. Ваш пароль: {password}",
        )

        return influencer


class LinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralLink
        fields = ['channel', 'link', 'count']


class BankDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDetails
        fields = ['id', 'inn', 'ogrn', 'registration_date', 'account_number', 'account_owner']


class OrganizationSerializer(serializers.ModelSerializer):
    bank_details = BankDetailsSerializer()

    class Meta:
        model = Organization
        fields = ['id', 'name', 'country', 'city', 'address', 'bank_details']

    def create(self, validated_data):
        bank_details_data = validated_data.pop('bank_details', None)

        bank_details = None
        if bank_details_data:
            bank_details = BankDetails.objects.create(**bank_details_data)

        organization = Organization.objects.create(bank_details=bank_details, **validated_data)

        return organization

    def update(self, instance, validated_data):
        bank_details_data = validated_data.pop('bank_details', None)

        # Обновление данных организации
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Обновление банковских данных
        if bank_details_data:
            if instance.bank_details:
                for attr, value in bank_details_data.items():
                    setattr(instance.bank_details, attr, value)
                instance.bank_details.save()
            else:
                bank_details = BankDetails.objects.create(**bank_details_data)
                instance.bank_details = bank_details
                instance.save()

        return instance


class InfluencerDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfluencerDocuments
        fields = ['number', 'photo', 'status']


class CustomAvatarField(serializers.ImageField):
    def to_internal_value(self, data):
        if data == "" or data is None:
            return None
        return super().to_internal_value(data)


class InfluencerDetailSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    date_of_birth = serializers.DateField(source='user.date_of_birth')
    avatar = CustomAvatarField(source='user.avatar', required=False)
    email = serializers.EmailField(source='user.email', read_only=True)
    telephone = serializers.CharField(source='user.telephone')
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    organization = OrganizationSerializer()
    document = InfluencerDocumentsSerializer(required=False, allow_null=True)
    referral_links = LinkSerializer(many=True, read_only=True)
    total_clicks = serializers.SerializerMethodField()
    total_rent_income = serializers.SerializerMethodField()

    class Meta:
        model = Influencer
        fields = ['id', 'user_id', 'first_name', 'last_name', 'referral_code', 'referral_links', 'total_clicks',
                  'commission', 'total_rent_income', 'organization', 'document', 'date_of_birth', 'avatar', 'email',
                  'telephone', 'email_1', 'email_2', 'telephone_1', 'telephone_2']
        read_only_fields = ['referral_code', 'total_clicks', 'total_rent_income', 'email', 'commission']

    def get_total_clicks(self, obj):
        return obj.referral_links.aggregate(total_count=Sum('count'))['total_count'] or 0

    def get_total_rent_income(self, obj):
        renter_users = obj.renters.values_list('user_id', flat=True)
        total_income = Trip.objects.filter(organizer_id__in=renter_users, status='finished').aggregate(
            total_cost=Sum('total_cost'))
        return total_income['total_cost'] or 0.00

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        self.update_user(instance, user_data)
        user = instance.user

        for field in ['email_1', 'email_2', 'telephone_1', 'telephone_2']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        for field, value in user_data.items():
            if field == 'avatar':
                if value is None:
                    if user.avatar:
                        user.avatar.delete(save=False)
                        user.avatar = None
                else:
                    setattr(user, field, value)
            else:
                setattr(user, field, value)

        organization_data = validated_data.pop('organization', None)
        if organization_data:
            self.update_organization(instance, organization_data)

        document_data = validated_data.pop('document', None)
        if document_data:
            self.update_document(instance, document_data)

        instance.save()
        return instance

    def update_user(self, instance, user_data):
        """Обновление данных пользователя."""
        user = instance.user
        for field in ['first_name', 'last_name', 'date_of_birth', 'telephone', 'avatar']:
            if field in user_data:
                setattr(user, field, user_data[field])
        user.save()

    def update_organization(self, instance, organization_data):
        """Обновление или создание организации и связанных объектов."""
        organization = instance.organization
        bank_details_data = organization_data.pop('bank_details', None)

        if not organization:
            bank_details = None
            if bank_details_data:
                bank_details = BankDetails.objects.create(**bank_details_data)

            organization = Organization.objects.create(bank_details=bank_details, **organization_data)
            instance.organization = organization
            instance.save()
        else:
            for attr, value in organization_data.items():
                setattr(organization, attr, value)
            organization.save()

            if bank_details_data:
                self.update_bank_details(organization, bank_details_data)

    def update_bank_details(self, organization, bank_details_data):
        """Обновление или создание банковских данных."""
        if organization.bank_details:
            for attr, value in bank_details_data.items():
                setattr(organization.bank_details, attr, value)
            organization.bank_details.save()
        else:
            bank_details = BankDetails.objects.create(**bank_details_data)
            organization.bank_details = bank_details
            organization.save()

    def update_document(self, instance, document_data):
        """Обновление документа инфлюенсера."""
        request = self.context.get('request')
        user_role = getattr(request.user, 'role', None) if request else None

        if document_data.get('status') != 'pending' and user_role not in ['admin', 'manager']:
            document_data['status'] = 'pending'

        if hasattr(instance, 'document') and instance.document:
            for attr, value in document_data.items():
                setattr(instance.document, attr, value)
            instance.document.save()
        else:
            document_data['influencer'] = instance
            document = InfluencerDocuments.objects.create(**document_data)
            instance.document = document


class InfluencerRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfluencerRequest
        fields = ['name', 'city', 'telephone', 'email', 'social', 'description']


class InfluencerRequestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfluencerRequest
        fields = ['id', 'name', 'city', 'telephone', 'email', 'social', 'description', 'created_at']


class ReferralLinkSerializer(serializers.ModelSerializer):
    influencer_id = serializers.IntegerField(source='influencer.id', read_only=True)
    influencer_name = serializers.CharField(source='influencer.user.first_name', read_only=True)
    turnover = serializers.SerializerMethodField()
    income = serializers.SerializerMethodField()

    class Meta:
        model = ReferralLink
        fields = ['id', 'influencer_id', 'influencer_name', 'channel', 'link', 'count', 'income', 'turnover', 'created_at']
        read_only_fields = ['id', 'influencer_id', 'influencer_name', 'link', 'count', 'income', 'turnover', 'created_at']

    def create(self, validated_data):
        validated_data['influencer'] = self.context['request'].user.influencer
        referral_link = ReferralLink.objects.create(**validated_data)
        return referral_link

    def get_turnover(self, obj):
        """
        Подсчет суммы успешных платежей для ссылок инфлюенсера.
        """
        registered_users = RegistrationSource.objects.filter(
            source_type='referral',
            source_details=obj.link
        ).values_list('user', flat=True)
        organizer_rents = RequestRent.objects.filter(
            organizer__in=registered_users
        )

        lessor_rents = RequestRent.objects.filter(
            content_type__model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic'],
            object_id__in=Vehicle.objects.filter(
                owner__in=registered_users
            ).values_list('id', flat=True)
        )

        all_rents = organizer_rents | lessor_rents

        turnover = Payment.objects.filter(
            request_rent__in=all_rents,
            status='success'
        ).aggregate(total_sum=Sum('amount'))['total_sum'] or 0

        return turnover

    def get_income(self, obj):
        """
        Подсчет дохода инфлюенсера на основе оборота и комиссии.
        """
        turnover = self.get_turnover(obj)
        commission = getattr(obj.influencer, 'commission', 0)
        return (turnover * commission) / 100


class QRCodeSerializer(serializers.ModelSerializer):
    influencer_name = serializers.CharField(source='influencer.user.first_name', read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    turnover = serializers.SerializerMethodField()
    income = serializers.SerializerMethodField()

    class Meta:
        model = QRCode
        fields = ['id', 'influencer', 'influencer_name', 'channel', 'referral_link', 'qr_code_url', 'created_at', 'count', 'turnover', 'income']
        read_only_fields = ['referral_link', 'qr_code_url', 'created_at', 'influencer', 'count', 'turnover', 'income', 'created_at']

    def get_qr_code_url(self, obj):
        """Возвращает полный URL к QR-коду."""
        request = self.context.get('request')
        if obj.qr_code_image:
            return request.build_absolute_uri(obj.qr_code_image.url) if request else obj.qr_code_image.url
        return None

    def get_turnover(self, obj):
        """
        Подсчет суммы успешных платежей для QR-кода инфлюенсера.
        """
        # request_rents = RequestRent.objects.filter(
        #     Q(organizer__renter__influencer=obj.influencer) |
        #     Q(content_type__model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic'],
        #       object_id__in=Vehicle.objects.filter(
        #           owner__renter__influencer=obj.influencer
        #       ).values_list('id', flat=True))
        # ).distinct()
        #
        # turnover = Payment.objects.filter(
        #     request_rent__in=request_rents,
        #     status='success'
        # ).aggregate(total_sum=Sum('amount'))['total_sum'] or 0
        #
        # return turnover

        registered_users = RegistrationSource.objects.filter(
            source_type='qr_code',
            source_details=obj.referral_link
        ).values_list('user', flat=True)
        organizer_rents = RequestRent.objects.filter(
            organizer__in=registered_users
        )

        lessor_rents = RequestRent.objects.filter(
            content_type__model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic'],
            object_id__in=Vehicle.objects.filter(
                owner__in=registered_users
            ).values_list('id', flat=True)
        )

        all_rents = organizer_rents | lessor_rents

        turnover = Payment.objects.filter(
            request_rent__in=all_rents,
            status='success'
        ).aggregate(total_sum=Sum('amount'))['total_sum'] or 0

        return turnover

    def get_income(self, obj):
        """
        Подсчет дохода инфлюенсера на основе оборота и комиссии.
        """
        turnover = self.get_turnover(obj)
        commission = getattr(obj.influencer, 'commission', 0)
        return (turnover * commission) / 100


class PromoCodeSerializer(serializers.ModelSerializer):
    turnover = serializers.SerializerMethodField()
    income = serializers.SerializerMethodField()

    class Meta:
        model = PromoCode
        fields = '__all__'
        read_only_fields = ['count', 'turnover', 'income', 'created_at']

    def validate(self, attrs):
        promo_type = attrs.get('type')
        total = attrs.get('total', 0)
        expiration_date = attrs.get('expiration_date')

        if not promo_type:
            raise serializers.ValidationError(
                'Поле "Тип промокода" обязательно для заполнения.'
            )

        if promo_type == 'percent' and total > 50:
            raise serializers.ValidationError(
                'Если выбран тип "Процент", "Количество" не может превышать 50.'
            )

        if expiration_date and expiration_date < now():
            raise serializers.ValidationError(
                'Срок действия промокода не может быть в прошлом.'
            )

        return attrs

    def get_turnover(self, obj):
        """
        Подсчет суммы успешных платежей для промокода.
        Учитывает:
        1. Платежи от пользователей, зарегистрировавшихся с промокодом
        2. Платежи, где промокод был использован напрямую в заявке
        """
        from django.db.models import Q
        
        if not obj.influencer:
            return 0

        # Получаем пользователей, зарегистрировавшихся с промокодом
        registered_users = RegistrationSource.objects.filter(
            source_type='promo',
            source_details=obj.title
        ).values_list('user', flat=True)

        # Находим заявки от этих пользователей
        organizer_rents = RequestRent.objects.filter(
            organizer__in=registered_users
        )

        lessor_rents = RequestRent.objects.filter(
            content_type__model__in=['auto', 'bike', 'ship', 'helicopter', 'specialtechnic'],
            object_id__in=Vehicle.objects.filter(
                owner__in=registered_users
            ).values_list('id', flat=True)
        )

        all_rents_from_registered = organizer_rents | lessor_rents

        # Считаем оборот с учетом обоих условий (избегаем дублирования через distinct)
        turnover = Payment.objects.filter(
            Q(request_rent__in=all_rents_from_registered) |  # От зарегистрированных пользователей
            Q(promo_code=obj),  # ИЛИ где промокод использован напрямую
            status='success'
        ).distinct().aggregate(total_sum=Sum('amount'))['total_sum'] or 0

        return turnover

    def get_income(self, obj):
        """
        Подсчет дохода инфлюенсера на основе оборота и комиссии.
        """
        if not obj.influencer:
            return 0

        turnover = self.get_turnover(obj)
        commission = getattr(obj.influencer, 'commission', 0)
        return (turnover * commission) / 100


class PromoCodeSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = ['title', 'type', 'total', 'expiration_date', 'created_at']


class WithdrawInfluencerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    avatar = CustomAvatarField(source='user.avatar', required=False)
    account_number = serializers.SerializerMethodField()

    class Meta:
        model = Influencer
        fields = ['id', 'first_name', 'last_name', 'avatar', 'account_number', ]

    def get_account_number(self, obj):
        if obj.organization and obj.organization.bank_details:
            return obj.organization.bank_details.account_number
        return None

class RequestWithdrawListSerializer(serializers.ModelSerializer):
    influencer = WithdrawInfluencerSerializer()

    class Meta:
        model = RequestWithdraw
        fields = ['id', 'influencer', 'created_at', 'amount', 'status']


class RequestWithdrawCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestWithdraw
        fields = ['amount']

    def validate_amount(self, value):
        """Проверяем, что сумма не превышает баланс инфлюенсера."""
        request = self.context['request']
        user = request.user

        if not hasattr(user, 'influencer') or not user.influencer:
            raise serializers.ValidationError("Пользователь не является партнером.")

        if value > user.influencer.account:
            raise serializers.ValidationError("Недостаточно средств на балансе.")

        return value

    def create(self, validated_data):
        """Автоматически назначаем инфлюенсера при создании заявки."""
        request = self.context['request']
        validated_data['influencer'] = request.user.influencer
        return super().create(validated_data)


class RequestWithdrawSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestWithdraw
        fields = '__all__'
        read_only_fields = ['id', 'influencer', 'created_at']

    def validate(self, attrs):
        """Проверка изменения статуса и причины отказа."""
        user = self.context['request'].user

        status = attrs.get('status', self.instance.status if self.instance else None)
        denied_reason = attrs.get('denied_reason')

        if self.instance and 'status' in attrs:
            if user.role not in ['admin', 'manager']:
                raise serializers.ValidationError({"status": "Вы не можете изменять статус."})

            if status == 'denied' and not denied_reason:
                raise serializers.ValidationError({"denied_reason": "Необходимо указать причину отказа."})

            if status != 'denied' and denied_reason:
                attrs['denied_reason'] = None

        return attrs

    def update(self, instance, validated_data):
        """Списание средств при подтверждении вывода."""
        status = validated_data.get('status', instance.status)

        if status == 'completed':
            if instance.amount > instance.influencer.account:
                raise serializers.ValidationError({"amount": "Недостаточно средств на балансе."})

            instance.influencer.account -= instance.amount
            instance.influencer.save()

        return super().update(instance, validated_data)


class PaymentSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    request_rent = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["date", "time", "amount", "request_rent"]

    def get_date(self, obj):
        return obj.updated_at.date()

    def get_time(self, obj):
        return obj.updated_at.strftime("%H:%M")

    def get_amount(self, obj):
        if obj.influencer and obj.influencer.commission:
            return (obj.amount / 100) * obj.influencer.commission
        return obj.amount

    def get_request_rent(self, obj):
        return str(obj.request_rent)
