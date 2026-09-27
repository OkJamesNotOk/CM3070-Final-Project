from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path("api/song/", views.search_song, name="search_song"),
]