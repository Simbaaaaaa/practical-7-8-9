from decimal import Decimal
from django.conf import settings
from django.db import models


class Profile(models.Model):
    ROLES = [
        ('client', 'Клиент'),
        ('washer', 'Мастер-мойщик'),
        ('shift_admin', 'Администратор смены'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Телефон', max_length=20, unique=True)
    role = models.CharField('Роль', max_length=20, choices=ROLES, default='client')

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.phone})'


class LoyaltyCard(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_card')
    basic_washes = models.PositiveIntegerField('Завершённых базовых моек', default=0)

    def __str__(self):
        return f'Карта {self.user.username}: {self.basic_washes}'


class BodyType(models.Model):
    name = models.CharField('Тип кузова', max_length=50, unique=True)
    price_multiplier = models.DecimalField('Коэффициент цены', max_digits=4, decimal_places=2, default=Decimal('1.00'))
    extra_minutes = models.PositiveSmallIntegerField('Доп. время (мин)', default=0)

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicles')
    brand = models.CharField('Марка', max_length=50)
    model = models.CharField('Модель', max_length=50)
    plate = models.CharField('Госномер', max_length=15, unique=True)
    body_type = models.ForeignKey(BodyType, on_delete=models.PROTECT, verbose_name='Тип кузова')
    photo = models.ImageField('Фото', upload_to='vehicles/', blank=True, null=True)

    def __str__(self):
        return f'{self.brand} {self.model} ({self.plate})'


class ServiceCategory(models.Model):
    name = models.CharField('Категория', max_length=80, unique=True)

    def __str__(self):
        return self.name


class Service(models.Model):
    BOX_TYPES = [
        ('wet', 'Мокрый бокс'),
        ('dry', 'Сухой бокс (детейлинг)'),
    ]
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name='services', verbose_name='Категория')
    name = models.CharField('Название услуги', max_length=120)
    description = models.TextField('Описание', blank=True)
    base_price = models.DecimalField('Базовая цена (₽)', max_digits=8, decimal_places=2)
    base_minutes = models.PositiveSmallIntegerField('Базовая длительность (мин)', default=40)
    required_box_type = models.CharField('Тип бокса', max_length=10, choices=BOX_TYPES, default='wet')
    is_basic_wash = models.BooleanField('Базовая мойка (учёт в штамп-карте)', default=True)

    def __str__(self):
        return self.name


class Box(models.Model):
    name = models.CharField('Бокс', max_length=60, unique=True)
    box_type = models.CharField('Тип бокса', max_length=10, choices=Service.BOX_TYPES, default='wet')
    is_active = models.BooleanField('Активен', default=True)

    def __str__(self):
        return self.name


class Booking(models.Model):
    STATUSES = [
        ('new', 'Новая'),
        ('confirmed', 'Подтверждена'),
        ('in_progress', 'В работе'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
    ]
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings', verbose_name='Клиент')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, verbose_name='Автомобиль')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name='Услуга')
    box = models.ForeignKey(Box, on_delete=models.PROTECT, verbose_name='Бокс')
    body_type_snapshot = models.CharField('Кузов на момент записи', max_length=50)
    starts_at = models.DateTimeField('Начало')
    ends_at = models.DateTimeField('Окончание')
    final_price = models.DecimalField('Итоговая цена', max_digits=8, decimal_places=2)
    discount = models.PositiveSmallIntegerField('Скидка, %', default=0)
    status = models.CharField('Статус', max_length=20, choices=STATUSES, default='new')

    class Meta:
        ordering = ['-starts_at']

    def __str__(self):
        return f'Запись #{self.pk}'
