from datetime import timedelta
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Box,Booking,LoyaltyCard
@transaction.atomic
def make_booking(client,vehicle,service,starts_at,comment=''):
    if vehicle.owner_id!=client.id: raise ValidationError('Нельзя записать чужой автомобиль.')
    if starts_at<=timezone.now(): raise ValidationError('Выберите время в будущем.')
    end=starts_at+timedelta(minutes=service.minutes_for(vehicle.body_type))
    selected=None
    for box in Box.objects.select_for_update().filter(box_type=service.box_type,active=True).order_by('pk'):
        busy=Booking.objects.filter(box=box,status__in=['new','confirmed','in_progress'],starts_at__lt=end,ends_at__gt=starts_at).exists()
        if not busy: selected=box; break
    if selected is None: raise ValidationError('Нет свободного бокса нужного типа на это время.')
    discount=0
    if service.is_basic_wash:
        card,_=LoyaltyCard.objects.select_for_update().get_or_create(user=client)
        if (card.basic_washes+1)%6==0: discount=50
    return Booking.objects.create(client=client,vehicle=vehicle,service=service,box=selected,starts_at=starts_at,ends_at=end,body_type_snapshot=vehicle.body_type.name,price=service.price_for(vehicle.body_type),discount=discount,comment=comment)
@transaction.atomic
def set_status(booking,status):
    item=Booking.objects.select_for_update().get(pk=booking.pk)
    old=item.status; item.status=status; item.save(update_fields=['status'])
    if status=='completed' and old!='completed' and item.service.is_basic_wash and not item.loyalty_counted:
        card,_=LoyaltyCard.objects.select_for_update().get_or_create(user=item.client)
        card.basic_washes+=1; card.save(update_fields=['basic_washes'])
        item.loyalty_counted=True; item.save(update_fields=['loyalty_counted'])
    return item
