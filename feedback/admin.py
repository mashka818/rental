from django.contrib import admin

from feedback.models import FeedbackRenter


@admin.register(FeedbackRenter)
class FeedbackRenterAdmin(admin.ModelAdmin):
    list_display = ('content', 'answer', 'user',  'timestamp')
    search_fields = ('user__email', 'renter__email', 'content')
    list_filter = ('timestamp',)
    readonly_fields = ('timestamp',)
