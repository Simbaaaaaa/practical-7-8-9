from django.shortcuts import render
from .models import Service
import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from .models import Booking, Box, LoyaltyCard, Profile, Service, Vehicle


def index(request):
    services = Service.objects.select_related('category').all()
    return render(request, 'garage/home.html', {'services': services})




def _get_role(user):
    if user.is_superuser:
        return 'shift_admin'
    profile = getattr(user, 'profile', None)
    return profile.role if profile else 'client'


@login_required
def cabinet(request):
    card, _ = LoyaltyCard.objects.get_or_create(user=request.user)
    bookings = (
        Booking.objects
        .filter(client=request.user)
        .select_related('service', 'vehicle', 'box')[:10]
    )
    return render(request, 'garage/cabinet.html', {'card': card, 'bookings': bookings})


@login_required
def vehicles(request):
    items = Vehicle.objects.filter(owner=request.user).select_related('body_type')
    return render(request, 'garage/vehicles.html', {'vehicles': items})


@login_required
def vehicle_delete(request, pk):
    obj = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Автомобиль удалён из гаража.')
        return redirect('vehicles')
    return render(request, 'garage/vehicle_confirm_delete.html', {'obj': obj})


@login_required
def bookings(request):
    role = _get_role(request.user)
    qs = Booking.objects.select_related('client', 'vehicle', 'service', 'box')
    if role == 'client':
        qs = qs.filter(client=request.user)

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    service_id = request.GET.get('service', '').strip()
    box_id = request.GET.get('box', '').strip()
    sort = request.GET.get('sort', '-starts_at').strip()

    if q:
        qs = qs.filter(
            Q(client__username__icontains=q)
            | Q(vehicle__plate__icontains=q)
            | Q(service__name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if service_id.isdigit():
        qs = qs.filter(service_id=int(service_id))
    if box_id.isdigit():
        qs = qs.filter(box_id=int(box_id))

    allowed_sorts = {'-starts_at', 'starts_at', '-final_price', 'final_price', 'status'}
    if sort in allowed_sorts:
        qs = qs.order_by(sort)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'page': page,
        'q': q,
        'status': status,
        'service_id': service_id,
        'box_id': box_id,
        'sort': sort,
        'statuses': Booking.STATUSES,
        'services': Service.objects.all(),
        'boxes': Box.objects.all(),
    }
    return render(request, 'garage/bookings.html', context)


@login_required
def booking_detail(request, pk):
    role = _get_role(request.user)
    b = get_object_or_404(Booking.objects.select_related('client', 'vehicle', 'service', 'box'), pk=pk)
    if role == 'client' and b.client != request.user:
        return HttpResponseForbidden('Доступ запрещён')

    if request.method == 'POST' and role in ('washer', 'shift_admin'):
        new_status = request.POST.get('status')
        valid_statuses = dict(Booking.STATUSES)
        if new_status in valid_statuses:
            was_completed = (b.status == 'completed')
            b.status = new_status
            b.save(update_fields=['status'])
            if new_status == 'completed' and not was_completed and b.service.is_basic_wash:
                card, _ = LoyaltyCard.objects.get_or_create(user=b.client)
                card.basic_washes += 1
                card.save(update_fields=['basic_washes'])
            messages.success(request, f'Статус записи #{b.pk} обновлён.')
            return redirect('booking_detail', pk=b.pk)

    return render(request, 'garage/booking_detail.html', {'b': b, 'role': role})


@login_required
def stats(request):
    if _get_role(request.user) != 'shift_admin':
        return HttpResponseForbidden('Доступно только администратору смены')

    agg = Booking.objects.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        revenue=Sum('final_price', filter=Q(status='completed')),
        avg=Avg('final_price', filter=Q(status='completed')),
    )
    total = agg['total'] or 0
    completed = agg['completed'] or 0
    revenue = agg['revenue'] or 0
    avg = agg['avg'] or 0
    ratio = round((completed / total) * 100, 1) if total else 0

    return render(request, 'garage/stats.html', {
        'total': total,
        'completed': completed,
        'revenue': revenue,
        'avg': avg,
        'ratio': ratio,
    })


@login_required
def stats_csv(request):
    if _get_role(request.user) != 'shift_admin':
        return HttpResponseForbidden('Доступно только администратору смены')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="garage_stats.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Клиент', 'Авто', 'Услуга', 'Бокс', 'Дата', 'Цена', 'Статус'])
    for b in Booking.objects.select_related('client', 'vehicle', 'service', 'box'):
        writer.writerow([b.pk, b.client, b.vehicle, b.service, b.box, b.starts_at, b.final_price, b.get_status_display()])
    return response