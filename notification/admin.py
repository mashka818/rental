from django.contrib import admin

from notification.models import Notification, FCMToken


class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'content', 'read_it', 'url', 'created_at', 'get_absolute_url']
    list_filter = ['read_it', 'user']
    search_fields = ['content', 'user__email']
    readonly_fields = ['get_absolute_url', 'created_at']

    def get_absolute_url(self, obj):
        return obj.get_absolute_url()

    get_absolute_url.short_description = 'Ссылка'

    def save_model(self, request, obj, form, change):
        # Custom behavior for save, if needed
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request, obj=None):
        return [
            ('Основная информация', {
                'fields': ('user', 'content', 'read_it', 'url')
            }),
            ('Дополнительно', {
                'fields': ('get_absolute_url',),
                'classes': ('collapse',)
            }),
        ]


class FCMTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'updated_at', 'last_used_at')
    list_filter = ('user', 'created_at')
    search_fields = ('token', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'last_used_at')

    def save_model(self, request, obj, form, change):
        # Custom behavior for save, if needed
        super().save_model(request, obj, form, change)


admin.site.register(Notification, NotificationAdmin)
admin.site.register(FCMToken, FCMTokenAdmin)
