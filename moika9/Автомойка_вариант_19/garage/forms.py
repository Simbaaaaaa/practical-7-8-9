import re
from datetime import timedelta
from decimal import Decimal
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Booking, Box, LoyaltyCard, Profile, Vehicle


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=50, required=True)
    phone = forms.CharField(label='Телефон', max_length=20, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'phone')

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError('Введите телефон в формате +7 900 000-00-00.')
        if Profile.objects.filter(phone=phone).exists():
            raise forms.ValidationError('Этот номер телефона уже зарегистрирован.')
        return phone


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ('brand', 'model', 'plate', 'body_type', 'photo')

    def clean_plate(self):
        plate = self.cleaned_data['plate'].strip().upper()
        if len(plate) < 6:
            raise forms.ValidationError('Введите корректный госномер автомобиля (например, А777АА77).')
        return plate


class BookingForm(forms.ModelForm):
    starts_at = forms.DateTimeField(
        label='Дата и время визита',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    class Meta:
        model = Booking
        fields = ('service', 'vehicle', 'starts_at')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(owner=user)

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get('service')
        vehicle = cleaned.get('vehicle')
        starts_at = cleaned.get('starts_at')

        if not (service and vehicle and starts_at):
            return cleaned

        if starts_at < timezone.now():
            self.add_error('starts_at', 'Нельзя оформить запись на прошедшее время.')
            return cleaned

        total_minutes = service.base_minutes + vehicle.body_type.extra_minutes
        ends_at = starts_at + timedelta(minutes=total_minutes)

        busy_box_ids = Booking.objects.filter(
            status__in=['new', 'confirmed', 'in_progress'],
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        ).values_list('box_id', flat=True)

        free_box = Box.objects.filter(
            is_active=True,
            box_type=service.required_box_type,
        ).exclude(id__in=busy_box_ids).first()

        if not free_box:
            self.add_error('starts_at', 'На выбранное время нет свободных боксов нужного типа.')
            return cleaned

        price = (service.base_price * vehicle.body_type.price_multiplier).quantize(Decimal('1.00'))
        discount = 0
        if service.is_basic_wash and self.user:
            card, _ = LoyaltyCard.objects.get_or_create(user=self.user)
            if (card.basic_washes + 1) % 6 == 0:
                discount = 50
                price = (price * Decimal('0.50')).quantize(Decimal('1.00'))

        cleaned['assigned_box'] = free_box
        cleaned['ends_at'] = ends_at
        cleaned['final_price'] = price
        cleaned['discount'] = discount
        return cleaned
