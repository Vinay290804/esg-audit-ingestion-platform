from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/dashboard/", views.dashboard, name="dashboard"),
    path("api/upload/", views.upload, name="upload"),
    path("api/activities/<int:activity_id>/review/", views.review_activity, name="review_activity"),
]
