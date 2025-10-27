from django.contrib import admin
from .models import RequestRent, Chat, Message, ChatSupport, MessageSupport
from django.utils.translation import gettext_lazy as _
from chat.models import Trip
from vehicle.models import Vehicle

# @admin.register(RequestRent)
# class RequestRentAdmin(admin.ModelAdmin):
#     list_display = ('id', 'status', 'organizer', 'start_date', 'end_date', 'vehicle')
#     search_fields = ('organizer__first_name', 'status')
#     list_filter = ('status', 'start_date', 'end_date')
#     list_display_links = ('organizer', 'vehicle')


# class TripAdmin(admin.ModelAdmin):
#     list_display = ('id', 'organizer', 'get_owner', 'start_date', 'end_date', 'get_object', 'total_cost', 'status')
#     list_filter = ('status', 'start_date', 'end_date', 'content_type')
#     search_fields = ('organizer__name', 'status', 'object_id')
#     date_hierarchy = 'start_date'
#     list_per_page = 20
#
#     def get_type(self, obj):
#         return obj.content_type.model
#     get_type.short_description = _('Тип транспорта')
#
#     def get_object(self, obj):
#         vehicle = Vehicle.objects.filter(id=obj.object_id).first()
#         return str(vehicle) if vehicle else None
#     get_object.short_description = _('Транспорт')
#
#     def get_owner(self, obj):
#         vehicle = Vehicle.objects.filter(id=obj.object_id).first()
#         return str(vehicle.owner) if vehicle and vehicle.owner else None
#     get_owner.short_description = _('Арендодатель')
#
#
# admin.site.register(Trip, TripAdmin)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'request_rent', 'participants_list')
    search_fields = ('request_rent__organizer__first_name', 'participants__first_name')
    inlines = [MessageInline]
    list_display_links = ('participants_list', 'request_rent')

    def participants_list(self, obj):
        return ", ".join([p.first_name for p in obj.participants.all()])


class MessageSupportInline(admin.TabularInline):
    model = MessageSupport
    extra = 0


@admin.register(ChatSupport)
class ChatSupportAdmin(admin.ModelAdmin):
    list_display = ('id', 'creator')
    search_fields = ('creator__first_name',)
    inlines = [MessageSupportInline]
