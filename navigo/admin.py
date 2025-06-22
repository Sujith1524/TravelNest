from django.contrib import admin
from .models import Package, Booking, UserProfile

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'vendor', 'destination', 'price', 'start_date', 'expiry_date', 'is_approved')
    list_filter = ('is_approved', 'vendor')
    search_fields = ('title', 'destination')
    fields = ('title', 'description', 'destination', 'price', 'duration', 'image', 'vendor', 'is_approved', 'start_date', 'expiry_date')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'package', 'booking_date', 'status', 'payment_status', 'number_of_persons')
    list_filter = ('status', 'payment_status')
    search_fields = ('user__username', 'package__title')
    fields = ('user', 'package', 'status', 'payment_status', 'order_id', 'razorpay_payment_id', 'number_of_persons')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone')
    search_fields = ('user__username',)