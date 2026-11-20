from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from garage.models import *
class Command(BaseCommand):
    help='Заполняет базу демонстрационными данными'
    def handle(self,*args,**kwargs):
        bodydata=[('Седан', '1.00', '1.00'),('Хэтчбек', '0.95', '0.95'),('Универсал', '1.10', '1.10'),('Кроссовер', '1.20', '1.15'),('Внедорожник', '1.30', '1.35'),('Минивэн', '1.30', '1.25')]
        bodies={}
        for n,p,t in bodydata:bodies[n],_=BodyType.objects.get_or_create(name=n,defaults={'price_factor':p,'time_factor':t})
        wash,_=Category.objects.get_or_create(name='Мойка'); det,_=Category.objects.get_or_create(name='Детейлинг')
        sd=[(wash,'Базовая мойка',900,40,'wet',True),(wash,'Комплексная мойка',1500,65,'wet',False),(wash,'Мойка двигателя',1800,50,'wet',False),(det,'Полировка кузова',6500,240,'detail',False),(det,'Химчистка салона',5500,210,'detail',False),(det,'Защитное покрытие',8000,180,'detail',False)]
        for c,n,p,m,bt,basic in sd:Service.objects.get_or_create(category=c,name=n,defaults={'base_price':p,'base_minutes':m,'box_type':bt,'is_basic_wash':basic})
        for i in range(1,4):Box.objects.get_or_create(name=f'Моечный бокс {i}',defaults={'box_type':'wet'})
        for i in range(1,3):Box.objects.get_or_create(name=f'Детейлинг-бокс {i}',defaults={'box_type':'detail'})
        demos=[('client_demo','client','client12345'),('washer_demo','washer','washer12345'),('admin_demo','shift_admin','admin12345')]
        users={}
        for name,role,pw in demos:
            u,new=User.objects.get_or_create(username=name,defaults={'email':name+'@example.com'})
            if new:u.set_password(pw);u.save()
            Profile.objects.update_or_create(user=u,defaults={'role':role});users[name]=u
        client=users['client_demo']; LoyaltyCard.objects.get_or_create(user=client)
        cars=[('Toyota','Camry','A111AA','Седан'),('Kia','Rio','A222AA','Хэтчбек'),('Skoda','Octavia','A333AA','Универсал'),('Hyundai','Tucson','A444AA','Кроссовер'),('Toyota','RAV4','A555AA','Внедорожник'),('VW','Caddy','A666AA','Минивэн')]
        vehicles=[]
        for brand,model,plate,body in cars:
            v,_=Vehicle.objects.get_or_create(plate=plate,defaults={'owner':client,'brand':brand,'model':model,'body_type':bodies[body]});vehicles.append(v)
        services=list(Service.objects.all());boxes=list(Box.objects.all());now=timezone.now().replace(minute=0,second=0,microsecond=0)
        for i in range(30):
            v=vehicles[i%len(vehicles)];s=services[i%len(services)];start=now+timedelta(days=i+2,hours=i%8);box=next(x for x in boxes if x.box_type==s.box_type)
            Booking.objects.get_or_create(client=client,vehicle=v,service=s,starts_at=start,defaults={'box':box,'ends_at':start+timedelta(minutes=s.minutes_for(v.body_type)),'body_type_snapshot':v.body_type.name,'price':s.price_for(v.body_type),'status':'completed' if i<12 else 'confirmed'})
        self.stdout.write(self.style.SUCCESS('Демо-данные созданы. Логины: client_demo/client12345, washer_demo/washer12345, admin_demo/admin12345'))
