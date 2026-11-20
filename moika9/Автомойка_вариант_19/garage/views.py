import csv
import json
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime
from .forms import BookingForm, RegisterForm, VehicleForm
from .models import Booking, Box, LoyaltyCard, Profile, Service, Vehicle


def _get_role(user):
    if user.is_superuser:
        return 'shift_admin'
    profile = getattr(user, 'profile', None)
    return profile.role if profile else 'client'


def home(request):
    services = Service.objects.select_related('category').all()
    return render(request, 'garage/home.html', {'services': services})


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, phone=form.cleaned_data['phone'], role='client')
            LoyaltyCard.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать в GARAGE.')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'garage/form.html', {'form': form, 'title': 'Регистрация'})


@login_required
def dashboard(request):
    card, _ = LoyaltyCard.objects.get_or_create(user=request.user)
    bookings = (
        Booking.objects
        .filter(client=request.user)
        .select_related('service', 'vehicle', 'box')[:10]
    )
    return render(request, 'garage/dashboard.html', {'card': card, 'bookings': bookings})


@login_required
def vehicles(request):
    items = Vehicle.objects.filter(owner=request.user).select_related('body_type')
    return render(request, 'garage/vehicles.html', {'vehicles': items})


@login_required
def vehicle_add(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES)
        if form.is_valid():
            v = form.save(commit=False)
            v.owner = request.user
            v.save()
            messages.success(request, 'Автомобиль добавлен в гараж.')
            return redirect('vehicles')
    else:
        form = VehicleForm()
    return render(request, 'garage/form.html', {'form': form, 'title': 'Добавить автомобиль'})


@login_required
def vehicle_edit(request, pk):
    obj = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные автомобиля обновлены.')
            return redirect('vehicles')
    else:
        form = VehicleForm(instance=obj)
    return render(request, 'garage/form.html', {'form': form, 'title': 'Изменить автомобиль'})


@login_required
def vehicle_delete(request, pk):
    obj = get_object_or_404(Vehicle, pk=pk, owner=request.user)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Автомобиль удалён из гаража.')
        return redirect('vehicles')
    return render(request, 'garage/delete.html', {'obj': obj})


@login_required
def booking_list(request):
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
def booking_add(request):
    if request.method == 'POST':
        form = BookingForm(request.POST, user=request.user)
        if form.is_valid():
            b = form.save(commit=False)
            b.client = request.user
            b.box = form.cleaned_data['assigned_box']
            b.body_type_snapshot = b.vehicle.body_type.name
            b.ends_at = form.cleaned_data['ends_at']
            b.final_price = form.cleaned_data['final_price']
            b.discount = form.cleaned_data['discount']
            b.status = 'confirmed'
            b.save()
            messages.success(request, f'Запись №{b.pk} оформлена в {b.box.name}!')
            return redirect('booking_detail', pk=b.pk)
    else:
        form = BookingForm(user=request.user)
    return render(request, 'garage/form.html', {'form': form, 'title': 'Новая запись'})


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

    return render(request, 'garage/detail.html', {'b': b, 'role': role})


@login_required
def analytics(request):
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

    states_data = [
        {'label': label, 'value': Booking.objects.filter(status=code).count()}
        for code, label in Booking.STATUSES
    ]

    return render(request, 'garage/analytics.html', {
        'total': total,
        'completed': completed,
        'revenue': revenue,
        'avg': avg,
        'ratio': ratio,
        'states': json.dumps(states_data, ensure_ascii=False),
    })


@login_required
def export_csv(request):
    if _get_role(request.user) != 'shift_admin':
        return HttpResponseForbidden('Доступно только администратору смены')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="garage_analytics.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Клиент', 'Авто', 'Услуга', 'Бокс', 'Дата', 'Цена', 'Статус'])
    for b in Booking.objects.select_related('client', 'vehicle', 'service', 'box'):
        writer.writerow([b.pk, b.client, b.vehicle, b.service, b.box, b.starts_at, b.final_price, b.get_status_display()])
    return response


def api_availability(request):
    service_id = request.GET.get('service')
    vehicle_id = request.GET.get('vehicle')
    starts_raw = request.GET.get('starts')

    if not (service_id and vehicle_id and starts_raw):
        return JsonResponse({'error': 'Выберите услугу, автомобиль и время.'}, status=400)

    service = get_object_or_404(Service, pk=service_id)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    starts_at = parse_datetime(starts_raw)
    if not starts_at:
        return JsonResponse({'error': 'Некорректный формат даты и времени.'}, status=400)

    minutes = service.base_minutes + vehicle.body_type.extra_minutes
    ends_at = starts_at + timedelta(minutes=minutes)

    busy_ids = Booking.objects.filter(
        status__in=['new', 'confirmed', 'in_progress'],
        starts_at__lt=ends_at,
        ends_at__gt=starts_at,
    ).values_list('box_id', flat=True)

    free_boxes = list(
        Box.objects.filter(is_active=True, box_type=service.required_box_type)
        .exclude(id__in=busy_ids)
        .values_list('name', flat=True)
    )

    price = (service.base_price * vehicle.body_type.price_multiplier).quantize(Decimal('1.00'))
    if request.user.is_authenticated and service.is_basic_wash:
        card, _ = LoyaltyCard.objects.get_or_create(user=request.user)
        if (card.basic_washes + 1) % 6 == 0:
            price = (price * Decimal('0.50')).quantize(Decimal('1.00'))
            return JsonResponse({
            'free_boxes': free_boxes,
            'minutes': minutes,
            'price': str(price),
            })