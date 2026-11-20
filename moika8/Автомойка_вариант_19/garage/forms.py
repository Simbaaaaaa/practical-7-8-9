from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Vehicle,Service
class RegisterForm(UserCreationForm):
    email=forms.EmailField(label='Электронная почта')
    first_name=forms.CharField(label='Имя')
    class Meta:
        model=User; fields=('username','first_name','email','password1','password2')
        labels={'username':'Логин'}
class VehicleForm(forms.ModelForm):
    class Meta:
        model=Vehicle; fields=('brand','model','plate','body_type','photo')
    def clean_photo(self):
        f=self.cleaned_data.get('photo')
        if f:
            if f.size>5*1024*1024: raise forms.ValidationError('Максимальный размер файла — 5 МБ.')
            if f.content_type not in ('image/jpeg','image/png','image/webp'): raise forms.ValidationError('Разрешены JPG, PNG и WEBP.')
        return f
class BookingForm(forms.Form):
    vehicle=forms.ModelChoiceField(queryset=Vehicle.objects.none(),label='Автомобиль')
    service=forms.ModelChoiceField(queryset=Service.objects.filter(active=True),label='Услуга')
    starts_at=forms.DateTimeField(label='Дата и время',widget=forms.DateTimeInput(attrs={'type':'datetime-local'}),input_formats=['%Y-%m-%dT%H:%M'])
    comment=forms.CharField(label='Комментарий',required=False,widget=forms.Textarea)
    def __init__(self,*args,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        if user: self.fields['vehicle'].queryset=Vehicle.objects.filter(owner=user)
