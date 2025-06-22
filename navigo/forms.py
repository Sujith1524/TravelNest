from django import forms
from .models import Package, UserProfile
from django.contrib.auth.models import User
from datetime import date, timedelta
import re

class PackageForm(forms.ModelForm):
    images = forms.ImageField(required=False, label="Images")

    class Meta:
        model = Package
        fields = ['title', 'description', 'destination', 'price', 'duration', 'expiry_date', 'start_date']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_price(self):
        price = self.cleaned_data['price']
        max_amount = 1_00_00_000  # Razorpay max amount in INR
        if price > max_amount:
            raise forms.ValidationError(f"Price cannot exceed ₹{max_amount:,}.")
        if price <= 0:
            raise forms.ValidationError("Price must be positive.")
        return price

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data['expiry_date']
        if expiry_date < date.today():
            raise forms.ValidationError("Expiry date cannot be in the past.")
        if expiry_date > date.today() + timedelta(days=365):
            raise forms.ValidationError("Expiry date cannot be more than a year from today.")
        return expiry_date

    def clean_start_date(self):
        start_date = self.cleaned_data['start_date']
        if start_date < date.today():
            raise forms.ValidationError("Start date cannot be in the past.")
        return start_date

class BookingForm(forms.Form):
    number_of_persons = forms.IntegerField(min_value=1, max_value=50, initial=1, label="Number of Persons")
    travel_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Travel Date")

    def __init__(self, *args, **kwargs):
        self.package = kwargs.pop('package', None)  # Allow package to be passed to the form
        super().__init__(*args, **kwargs)

    def clean_travel_date(self):
        travel_date = self.cleaned_data['travel_date']
        if travel_date < date.today():
            raise forms.ValidationError("Travel date cannot be in the past.")
        if self.package:
            if travel_date < self.package.start_date:
                raise forms.ValidationError("Travel date cannot be before the package start date.")
            if travel_date > self.package.expiry_date:
                raise forms.ValidationError("Travel date cannot be after the package expiry date.")
        return travel_date

class ProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    phone = forms.CharField(max_length=15, required=False)
    profile_image = forms.ImageField(required=False, label="Profile Image")

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            try:
                user_profile = self.instance.userprofile
                self.fields['phone'].initial = user_profile.phone or ''
                self.fields['profile_image'].initial = user_profile.profile_image
            except UserProfile.DoesNotExist:
                self.fields['phone'].initial = ''
                self.fields['profile_image'].initial = None

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if not re.match(r'^\+?\d{10,15}$', phone):
                raise forms.ValidationError('Enter a valid phone number (e.g., +1234567890 or 1234567890).')
        return phone

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image')
        if image:
            if image.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError("Image file too large (max 5MB).")
            if not image.content_type in ['image/jpeg', 'image/png']:
                raise forms.ValidationError("Only JPEG and PNG images are allowed.")
        return image

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            user_profile, created = UserProfile.objects.get_or_create(user=user)
            user_profile.phone = self.cleaned_data['phone'] or None
            user_profile.profile_image = self.cleaned_data['profile_image']
            user_profile.save()
        return user