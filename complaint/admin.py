from django.contrib import admin
from tornado.escape import linkify

from complaint.models import Complaint, ComplaintForFeedback, ComplaintForFeedbackRenter


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_filter = ['topic', 'vehicle']
    list_display = ['id', linkify('user'), linkify('vehicle'), 'topic', 'description']


class BaseComplaintFeedbackAdmin(admin.ModelAdmin):
    list_filter = ['feedback', 'user', 'topic']
    list_display = ['user', 'topic', 'description', 'feedback']
    list_display_links = ['feedback', 'user']


@admin.register(ComplaintForFeedback)
class ComplaintForFeedbackAdmin(BaseComplaintFeedbackAdmin):
    pass


@admin.register(ComplaintForFeedbackRenter)
class ComplaintForFeedbackRenterAdmin(BaseComplaintFeedbackAdmin):
    pass
