from django.contrib import admin
from .models import BodyType, Booking, Box, LoyaltyCard, Profile, Service, ServiceCategory, Vehicle

admin.site.register([Profile, LoyaltyCard, BodyType, Vehicle, ServiceCategory, Service, Box, Booking])
