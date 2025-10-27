from django.urls import path

from report.views import LessorReportView, InfluencerReportView, UserRegistrationReportView, \
    FranchiseReportViewV2

urlpatterns = [
    path('lessor_report/', LessorReportView.as_view(), name='lessor_report'),
    path('influencer_report/', InfluencerReportView.as_view(), name='influencer_report'),
    path('franchise_report_v2/', FranchiseReportViewV2.as_view(), name='franchise_report'),
    path('user-registration-report/', UserRegistrationReportView.as_view(), name='user-registration-report'),
]
