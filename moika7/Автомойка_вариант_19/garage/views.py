from django.shortcuts import render
from .models import Service


def index(request):
    services = Service.objects.select_related('category').all()
    return render(request, 'garage/home.html', {'services': services})
